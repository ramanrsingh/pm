import hashlib
import json
import secrets
import sqlite3
from pathlib import Path

# TODO: Replace with environment-variable-based credentials before production.
MVP_USERNAME = "user"
MVP_PASSWORD = "password"

DEFAULT_COLUMNS = [
    ("col-backlog", "Backlog", 0),
    ("col-discovery", "Discovery", 1),
    ("col-progress", "In Progress", 2),
    ("col-review", "Review", 3),
    ("col-done", "Done", 4),
]

DEFAULT_CARDS = [
    (
        "card-1",
        "col-backlog",
        "Align roadmap themes",
        "Draft quarterly themes with impact statements and metrics.",
        0,
    ),
    (
        "card-2",
        "col-backlog",
        "Gather customer signals",
        "Review support tags, sales notes, and churn feedback.",
        1,
    ),
    (
        "card-3",
        "col-discovery",
        "Prototype analytics view",
        "Sketch initial dashboard layout and key drill-downs.",
        0,
    ),
    (
        "card-4",
        "col-progress",
        "Refine status language",
        "Standardize column labels and tone across the board.",
        0,
    ),
    (
        "card-5",
        "col-progress",
        "Design card layout",
        "Add hierarchy and spacing for scanning dense lists.",
        1,
    ),
    (
        "card-6",
        "col-review",
        "QA micro-interactions",
        "Verify hover, focus, and loading states.",
        0,
    ),
    (
        "card-7",
        "col-done",
        "Ship marketing page",
        "Final copy approved and asset pack delivered.",
        0,
    ),
    (
        "card-8",
        "col-done",
        "Close onboarding sprint",
        "Document release notes and share internally.",
        1,
    ),
]

# Sentinel used to temporarily park a card outside valid position space while
# source and destination columns are reindexed, avoiding UNIQUE(column_id, position)
# constraint collisions during cross-column moves.
_REINDEX_PLACEHOLDER = -(10 ** 6)

# Current schema version. Increment when making breaking schema changes.
_SCHEMA_VERSION = 2


class BoardNotFoundError(Exception):
    pass


class ColumnNotFoundError(Exception):
    pass


class CardNotFoundError(Exception):
    pass


class UserAlreadyExistsError(Exception):
    pass


class BoardPermissionError(Exception):
    pass


def _connect(db_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON;")
    return connection


def _hash_password(value: str) -> str:
    """Hash a password with a random salt using scrypt. Returns 'salt_hex:hash_hex'."""
    salt = secrets.token_bytes(16)
    hash_bytes = hashlib.scrypt(value.encode("utf-8"), salt=salt, n=16384, r=8, p=1)
    return f"{salt.hex()}:{hash_bytes.hex()}"


def _verify_password(value: str, stored: str) -> bool:
    """Verify a plaintext value against a stored scrypt hash."""
    try:
        salt_hex, hash_hex = stored.split(":", 1)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(hash_hex)
        actual = hashlib.scrypt(value.encode("utf-8"), salt=salt, n=16384, r=8, p=1)
        return secrets.compare_digest(actual, expected)
    except Exception:
        return False


def _get_schema_version(connection: sqlite3.Connection) -> int:
    return int(connection.execute("PRAGMA user_version").fetchone()[0])


def _set_schema_version(connection: sqlite3.Connection, version: int) -> None:
    connection.execute(f"PRAGMA user_version = {version}")


def _migrate_v1_to_v2(connection: sqlite3.Connection) -> None:
    """Remove UNIQUE(user_id) constraint from boards to allow multiple boards per user."""
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS boards_new (
            id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL DEFAULT 'Project Board',
            settings_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        INSERT OR IGNORE INTO boards_new SELECT * FROM boards;

        DROP TABLE boards;

        ALTER TABLE boards_new RENAME TO boards;

        CREATE INDEX IF NOT EXISTS idx_boards_user_id ON boards(user_id);
        """
    )
    _set_schema_version(connection, 2)


def initialize_database(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with _connect(db_path) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              username TEXT NOT NULL UNIQUE,
              password_hash TEXT NOT NULL,
              created_at TEXT NOT NULL DEFAULT (datetime('now')),
              updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS boards (
              id TEXT PRIMARY KEY,
              user_id INTEGER NOT NULL,
              name TEXT NOT NULL DEFAULT 'Project Board',
              settings_json TEXT NOT NULL DEFAULT '{}',
              created_at TEXT NOT NULL DEFAULT (datetime('now')),
              updated_at TEXT NOT NULL DEFAULT (datetime('now')),
              FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS board_columns (
              id TEXT PRIMARY KEY,
              board_id TEXT NOT NULL,
              title TEXT NOT NULL,
              position INTEGER NOT NULL,
              created_at TEXT NOT NULL DEFAULT (datetime('now')),
              updated_at TEXT NOT NULL DEFAULT (datetime('now')),
              FOREIGN KEY (board_id) REFERENCES boards(id) ON DELETE CASCADE,
              UNIQUE (board_id, position)
            );

            CREATE TABLE IF NOT EXISTS cards (
              id TEXT PRIMARY KEY,
              board_id TEXT NOT NULL,
              column_id TEXT NOT NULL,
              title TEXT NOT NULL,
              details TEXT NOT NULL DEFAULT '',
              position INTEGER NOT NULL,
              metadata_json TEXT NOT NULL DEFAULT '{}',
              created_at TEXT NOT NULL DEFAULT (datetime('now')),
              updated_at TEXT NOT NULL DEFAULT (datetime('now')),
              FOREIGN KEY (board_id) REFERENCES boards(id) ON DELETE CASCADE,
              FOREIGN KEY (column_id) REFERENCES board_columns(id) ON DELETE CASCADE,
              UNIQUE (column_id, position)
            );

            CREATE TABLE IF NOT EXISTS chat_threads (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              board_id TEXT NOT NULL,
              title TEXT,
              created_at TEXT NOT NULL DEFAULT (datetime('now')),
              updated_at TEXT NOT NULL DEFAULT (datetime('now')),
              FOREIGN KEY (board_id) REFERENCES boards(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS chat_messages (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              thread_id INTEGER NOT NULL,
              role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
              content TEXT NOT NULL,
              metadata_json TEXT NOT NULL DEFAULT '{}',
              created_at TEXT NOT NULL DEFAULT (datetime('now')),
              FOREIGN KEY (thread_id) REFERENCES chat_threads(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_boards_user_id ON boards(user_id);
            CREATE INDEX IF NOT EXISTS idx_columns_board_id_position ON board_columns(board_id, position);
            CREATE INDEX IF NOT EXISTS idx_cards_board_id ON cards(board_id);
            CREATE INDEX IF NOT EXISTS idx_cards_column_id_position ON cards(column_id, position);
            CREATE INDEX IF NOT EXISTS idx_threads_board_id ON chat_threads(board_id);
            CREATE INDEX IF NOT EXISTS idx_messages_thread_id_created_at ON chat_messages(thread_id, created_at);
            """
        )

        # Run migrations for existing databases.
        version = _get_schema_version(connection)
        if version < 2:
            # Check if boards table has the old UNIQUE(user_id) constraint by trying to detect it.
            # In fresh DBs created above, the constraint is already absent; skip migration.
            index_rows = connection.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='boards'"
            ).fetchall()
            index_names = [row["name"] for row in index_rows]
            # Old schema had a sqlite_autoindex for the unique constraint.
            has_unique_index = any("autoindex" in name.lower() for name in index_names)
            if has_unique_index:
                _migrate_v1_to_v2(connection)
            else:
                _set_schema_version(connection, _SCHEMA_VERSION)

        _seed_mvp_user_data(connection)


def _seed_mvp_user_data(connection: sqlite3.Connection) -> None:
    # Always update the password hash to ensure it uses the current algorithm.
    connection.execute(
        """
        INSERT INTO users (username, password_hash)
        VALUES (?, ?)
        ON CONFLICT(username) DO UPDATE SET password_hash = excluded.password_hash
        """,
        (MVP_USERNAME, _hash_password(MVP_PASSWORD)),
    )

    user_row = connection.execute(
        "SELECT id FROM users WHERE username = ?",
        (MVP_USERNAME,),
    ).fetchone()
    if user_row is None:
        raise RuntimeError("Failed to seed MVP user.")

    board_id = f"board-{user_row['id']}"
    connection.execute(
        """
        INSERT INTO boards (id, user_id, name)
        VALUES (?, ?, 'Project Board')
        ON CONFLICT(id) DO NOTHING
        """,
        (board_id, user_row["id"]),
    )

    existing_columns = connection.execute(
        "SELECT COUNT(1) AS count FROM board_columns WHERE board_id = ?",
        (board_id,),
    ).fetchone()["count"]

    if existing_columns == 0:
        connection.executemany(
            """
            INSERT INTO board_columns (id, board_id, title, position)
            VALUES (?, ?, ?, ?)
            """,
            [(column_id, board_id, title, position) for column_id, title, position in DEFAULT_COLUMNS],
        )

    existing_cards = connection.execute(
        "SELECT COUNT(1) AS count FROM cards WHERE board_id = ?",
        (board_id,),
    ).fetchone()["count"]

    if existing_cards == 0:
        connection.executemany(
            """
            INSERT INTO cards (id, board_id, column_id, title, details, position, metadata_json)
            VALUES (?, ?, ?, ?, ?, ?, '{}')
            """,
            [
                (card_id, board_id, column_id, title, details, position)
                for card_id, column_id, title, details, position in DEFAULT_CARDS
            ],
        )


def user_exists(db_path: Path, username: str) -> bool:
    with _connect(db_path) as connection:
        row = connection.execute(
            "SELECT 1 FROM users WHERE username = ?",
            (username,),
        ).fetchone()
        return row is not None


def verify_credentials(db_path: Path, username: str, password: str) -> bool:
    with _connect(db_path) as connection:
        row = connection.execute(
            "SELECT password_hash FROM users WHERE username = ?",
            (username,),
        ).fetchone()
        if row is None:
            return False
        return _verify_password(password, row["password_hash"])


def register_user(db_path: Path, username: str, password: str) -> None:
    """Create a new user account. Raises UserAlreadyExistsError if username is taken."""
    with _connect(db_path) as connection:
        existing = connection.execute(
            "SELECT 1 FROM users WHERE username = ?",
            (username,),
        ).fetchone()
        if existing is not None:
            raise UserAlreadyExistsError(username)

        connection.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (username, _hash_password(password)),
        )
        user_row = connection.execute(
            "SELECT id FROM users WHERE username = ?",
            (username,),
        ).fetchone()
        board_id = f"board-{user_row['id']}"
        connection.execute(
            "INSERT INTO boards (id, user_id, name) VALUES (?, ?, 'Project Board')",
            (board_id, user_row["id"]),
        )
        connection.executemany(
            "INSERT INTO board_columns (id, board_id, title, position) VALUES (?, ?, ?, ?)",
            [(f"{column_id}-u{user_row['id']}", board_id, title, position) for column_id, title, position in DEFAULT_COLUMNS],
        )


def change_password(db_path: Path, username: str, current_password: str, new_password: str) -> bool:
    """Change a user's password. Returns False if current_password is wrong."""
    if not verify_credentials(db_path, username, current_password):
        return False
    with _connect(db_path) as connection:
        connection.execute(
            "UPDATE users SET password_hash = ?, updated_at = datetime('now') WHERE username = ?",
            (_hash_password(new_password), username),
        )
    return True


def _get_board_id(connection: sqlite3.Connection, username: str) -> str:
    """Return the first/default board id for the user."""
    board_row = connection.execute(
        """
        SELECT b.id AS board_id
        FROM boards b
        INNER JOIN users u ON u.id = b.user_id
        WHERE u.username = ?
        ORDER BY b.created_at ASC
        LIMIT 1
        """,
        (username,),
    ).fetchone()
    if board_row is None:
        raise BoardNotFoundError(f"Board not found for user: {username}")
    return board_row["board_id"]


def _validate_board_ownership(connection: sqlite3.Connection, username: str, board_id: str) -> None:
    """Raise BoardNotFoundError if board_id does not belong to username."""
    row = connection.execute(
        """
        SELECT b.id
        FROM boards b
        INNER JOIN users u ON u.id = b.user_id
        WHERE u.username = ? AND b.id = ?
        """,
        (username, board_id),
    ).fetchone()
    if row is None:
        raise BoardNotFoundError(f"Board {board_id!r} not found for user {username!r}.")


def _build_board_payload(connection: sqlite3.Connection, board_id: str) -> dict:
    board_row = connection.execute(
        "SELECT id, name FROM boards WHERE id = ?",
        (board_id,),
    ).fetchone()

    column_rows = connection.execute(
        """
        SELECT id, title
        FROM board_columns
        WHERE board_id = ?
        ORDER BY position ASC
        """,
        (board_id,),
    ).fetchall()

    card_rows = connection.execute(
        """
        SELECT id, column_id, title, details, metadata_json
        FROM cards
        WHERE board_id = ?
        ORDER BY column_id ASC, position ASC
        """,
        (board_id,),
    ).fetchall()

    cards_by_column: dict[str, list[str]] = {column["id"]: [] for column in column_rows}
    cards: dict[str, dict] = {}

    for row in card_rows:
        card_id = row["id"]
        column_id = row["column_id"]
        cards_by_column.setdefault(column_id, []).append(card_id)
        cards[card_id] = {
            "id": card_id,
            "title": row["title"],
            "details": row["details"],
            "metadata": json.loads(row["metadata_json"]),
        }

    columns = [
        {
            "id": column["id"],
            "title": column["title"],
            "cardIds": cards_by_column.get(column["id"], []),
        }
        for column in column_rows
    ]

    return {
        "id": board_id,
        "name": board_row["name"] if board_row else "Project Board",
        "columns": columns,
        "cards": cards,
    }


def get_board_for_user(db_path: Path, username: str) -> dict:
    with _connect(db_path) as connection:
        board_id = _get_board_id(connection, username)
        return _build_board_payload(connection, board_id)


def get_board_by_id(db_path: Path, username: str, board_id: str) -> dict:
    with _connect(db_path) as connection:
        _validate_board_ownership(connection, username, board_id)
        return _build_board_payload(connection, board_id)


def list_boards_for_user(db_path: Path, username: str) -> list[dict]:
    with _connect(db_path) as connection:
        rows = connection.execute(
            """
            SELECT b.id, b.name, b.created_at
            FROM boards b
            INNER JOIN users u ON u.id = b.user_id
            WHERE u.username = ?
            ORDER BY b.created_at ASC
            """,
            (username,),
        ).fetchall()
        return [{"id": row["id"], "name": row["name"], "createdAt": row["created_at"]} for row in rows]


def create_board(db_path: Path, username: str, name: str) -> dict:
    """Create a new board for a user with default columns. Returns the new board payload."""
    with _connect(db_path) as connection:
        user_row = connection.execute(
            "SELECT id FROM users WHERE username = ?",
            (username,),
        ).fetchone()
        if user_row is None:
            raise BoardNotFoundError(f"User {username!r} not found.")

        board_id = f"board-{secrets.token_hex(8)}"
        connection.execute(
            "INSERT INTO boards (id, user_id, name) VALUES (?, ?, ?)",
            (board_id, user_row["id"], name),
        )

        for column_id, title, position in DEFAULT_COLUMNS:
            new_col_id = f"{column_id}-{secrets.token_hex(4)}"
            connection.execute(
                "INSERT INTO board_columns (id, board_id, title, position) VALUES (?, ?, ?, ?)",
                (new_col_id, board_id, title, position),
            )

        return _build_board_payload(connection, board_id)


def rename_board(db_path: Path, username: str, board_id: str, name: str) -> dict:
    with _connect(db_path) as connection:
        _validate_board_ownership(connection, username, board_id)
        connection.execute(
            "UPDATE boards SET name = ?, updated_at = datetime('now') WHERE id = ?",
            (name, board_id),
        )
        return _build_board_payload(connection, board_id)


def delete_board(db_path: Path, username: str, board_id: str) -> None:
    with _connect(db_path) as connection:
        _validate_board_ownership(connection, username, board_id)
        # Ensure user has at least one board remaining after deletion.
        board_count = connection.execute(
            """
            SELECT COUNT(1) AS cnt
            FROM boards b
            INNER JOIN users u ON u.id = b.user_id
            WHERE u.username = ?
            """,
            (username,),
        ).fetchone()["cnt"]
        if board_count <= 1:
            raise BoardPermissionError("Cannot delete the last board.")
        connection.execute("DELETE FROM boards WHERE id = ?", (board_id,))


def rename_column(db_path: Path, username: str, column_id: str, title: str) -> dict:
    with _connect(db_path) as connection:
        board_id = _get_board_id(connection, username)
        result = connection.execute(
            """
            UPDATE board_columns
            SET title = ?, updated_at = datetime('now')
            WHERE board_id = ? AND id = ?
            """,
            (title, board_id, column_id),
        )
        if result.rowcount == 0:
            raise ColumnNotFoundError(column_id)
        return _build_board_payload(connection, board_id)


def rename_column_on_board(db_path: Path, username: str, board_id: str, column_id: str, title: str) -> dict:
    with _connect(db_path) as connection:
        _validate_board_ownership(connection, username, board_id)
        result = connection.execute(
            """
            UPDATE board_columns
            SET title = ?, updated_at = datetime('now')
            WHERE board_id = ? AND id = ?
            """,
            (title, board_id, column_id),
        )
        if result.rowcount == 0:
            raise ColumnNotFoundError(column_id)
        return _build_board_payload(connection, board_id)


def add_column(db_path: Path, username: str, board_id: str, title: str) -> dict:
    """Add a new column to the specified board."""
    with _connect(db_path) as connection:
        _validate_board_ownership(connection, username, board_id)
        next_position = connection.execute(
            "SELECT COALESCE(MAX(position), -1) + 1 AS next_pos FROM board_columns WHERE board_id = ?",
            (board_id,),
        ).fetchone()["next_pos"]
        column_id = f"col-{secrets.token_hex(6)}"
        connection.execute(
            "INSERT INTO board_columns (id, board_id, title, position) VALUES (?, ?, ?, ?)",
            (column_id, board_id, title, int(next_position)),
        )
        return _build_board_payload(connection, board_id)


def delete_column(db_path: Path, username: str, board_id: str, column_id: str) -> dict:
    """Delete a column (and all its cards) from the specified board."""
    with _connect(db_path) as connection:
        _validate_board_ownership(connection, username, board_id)
        col_row = connection.execute(
            "SELECT id FROM board_columns WHERE board_id = ? AND id = ?",
            (board_id, column_id),
        ).fetchone()
        if col_row is None:
            raise ColumnNotFoundError(column_id)
        connection.execute("DELETE FROM board_columns WHERE id = ?", (column_id,))
        return _build_board_payload(connection, board_id)


# === Connection-scoped mutation helpers (used by public API and batch operations) ===


def _do_create_card(
    connection: sqlite3.Connection,
    board_id: str,
    column_id: str,
    title: str,
    details: str,
) -> None:
    column_row = connection.execute(
        "SELECT 1 FROM board_columns WHERE board_id = ? AND id = ?",
        (board_id, column_id),
    ).fetchone()
    if column_row is None:
        raise ColumnNotFoundError(column_id)

    next_position = connection.execute(
        "SELECT COALESCE(MAX(position), -1) + 1 AS next_pos FROM cards WHERE column_id = ?",
        (column_id,),
    ).fetchone()["next_pos"]

    card_id = f"card-{secrets.token_hex(6)}"
    connection.execute(
        """
        INSERT INTO cards (id, board_id, column_id, title, details, position, metadata_json)
        VALUES (?, ?, ?, ?, ?, ?, '{}')
        """,
        (card_id, board_id, column_id, title, details, int(next_position)),
    )


def _do_update_card(
    connection: sqlite3.Connection,
    board_id: str,
    card_id: str,
    title: str | None,
    details: str | None,
) -> None:
    existing = connection.execute(
        "SELECT id FROM cards WHERE board_id = ? AND id = ?",
        (board_id, card_id),
    ).fetchone()
    if existing is None:
        raise CardNotFoundError(card_id)

    if title is None and details is None:
        return

    if title is not None:
        connection.execute(
            "UPDATE cards SET title = ?, updated_at = datetime('now') WHERE id = ?",
            (title, card_id),
        )

    if details is not None:
        connection.execute(
            "UPDATE cards SET details = ?, updated_at = datetime('now') WHERE id = ?",
            (details, card_id),
        )


def _do_move_card(
    connection: sqlite3.Connection,
    board_id: str,
    card_id: str,
    destination_column_id: str,
    destination_position: int | None,
) -> None:
    card_row = connection.execute(
        "SELECT id, column_id FROM cards WHERE board_id = ? AND id = ?",
        (board_id, card_id),
    ).fetchone()
    if card_row is None:
        raise CardNotFoundError(card_id)

    source_column_id = str(card_row["column_id"])

    destination_column = connection.execute(
        "SELECT id FROM board_columns WHERE board_id = ? AND id = ?",
        (board_id, destination_column_id),
    ).fetchone()
    if destination_column is None:
        raise ColumnNotFoundError(destination_column_id)

    source_ids = _load_ordered_card_ids(connection, source_column_id)
    if card_id not in source_ids:
        raise CardNotFoundError(card_id)

    source_ids.remove(card_id)

    if source_column_id == destination_column_id:
        insert_position = len(source_ids)
        if destination_position is not None:
            insert_position = max(0, min(destination_position, len(source_ids)))
        source_ids.insert(insert_position, card_id)
        _reindex_column(connection, source_column_id, source_ids)
        return

    destination_ids = _load_ordered_card_ids(connection, destination_column_id)
    insert_position = len(destination_ids)
    if destination_position is not None:
        insert_position = max(0, min(destination_position, len(destination_ids)))
    destination_ids.insert(insert_position, card_id)

    # Park the card at a placeholder position outside valid space so that
    # source reindexing does not collide with the card's previous position.
    connection.execute(
        """
        UPDATE cards
        SET column_id = ?, position = ?, updated_at = datetime('now')
        WHERE id = ?
        """,
        (destination_column_id, _REINDEX_PLACEHOLDER, card_id),
    )

    _reindex_column(connection, source_column_id, source_ids)
    _reindex_column(connection, destination_column_id, destination_ids)


# === Public API functions ===


def create_card(db_path: Path, username: str, column_id: str, title: str, details: str) -> dict:
    with _connect(db_path) as connection:
        board_id = _get_board_id(connection, username)
        _do_create_card(connection, board_id, column_id, title, details)
        return _build_board_payload(connection, board_id)


def create_card_on_board(
    db_path: Path, username: str, board_id: str, column_id: str, title: str, details: str
) -> dict:
    with _connect(db_path) as connection:
        _validate_board_ownership(connection, username, board_id)
        _do_create_card(connection, board_id, column_id, title, details)
        return _build_board_payload(connection, board_id)


def update_card(
    db_path: Path,
    username: str,
    card_id: str,
    title: str | None,
    details: str | None,
) -> dict:
    with _connect(db_path) as connection:
        board_id = _get_board_id(connection, username)
        _do_update_card(connection, board_id, card_id, title, details)
        return _build_board_payload(connection, board_id)


def update_card_on_board(
    db_path: Path,
    username: str,
    board_id: str,
    card_id: str,
    title: str | None,
    details: str | None,
) -> dict:
    with _connect(db_path) as connection:
        _validate_board_ownership(connection, username, board_id)
        _do_update_card(connection, board_id, card_id, title, details)
        return _build_board_payload(connection, board_id)


def delete_card(db_path: Path, username: str, card_id: str) -> dict:
    with _connect(db_path) as connection:
        board_id = _get_board_id(connection, username)

        card_row = connection.execute(
            "SELECT column_id, position FROM cards WHERE board_id = ? AND id = ?",
            (board_id, card_id),
        ).fetchone()
        if card_row is None:
            raise CardNotFoundError(card_id)

        column_id = str(card_row["column_id"])
        position = int(card_row["position"])

        connection.execute("DELETE FROM cards WHERE id = ?", (card_id,))
        connection.execute(
            "UPDATE cards SET position = position - 1 WHERE column_id = ? AND position > ?",
            (column_id, position),
        )

        return _build_board_payload(connection, board_id)


def delete_card_on_board(db_path: Path, username: str, board_id: str, card_id: str) -> dict:
    with _connect(db_path) as connection:
        _validate_board_ownership(connection, username, board_id)

        card_row = connection.execute(
            "SELECT column_id, position FROM cards WHERE board_id = ? AND id = ?",
            (board_id, card_id),
        ).fetchone()
        if card_row is None:
            raise CardNotFoundError(card_id)

        column_id = str(card_row["column_id"])
        position = int(card_row["position"])

        connection.execute("DELETE FROM cards WHERE id = ?", (card_id,))
        connection.execute(
            "UPDATE cards SET position = position - 1 WHERE column_id = ? AND position > ?",
            (column_id, position),
        )

        return _build_board_payload(connection, board_id)


def move_card(
    db_path: Path,
    username: str,
    card_id: str,
    destination_column_id: str,
    destination_position: int | None,
) -> dict:
    with _connect(db_path) as connection:
        board_id = _get_board_id(connection, username)
        _do_move_card(connection, board_id, card_id, destination_column_id, destination_position)
        return _build_board_payload(connection, board_id)


def move_card_on_board(
    db_path: Path,
    username: str,
    board_id: str,
    card_id: str,
    destination_column_id: str,
    destination_position: int | None,
) -> dict:
    with _connect(db_path) as connection:
        _validate_board_ownership(connection, username, board_id)
        _do_move_card(connection, board_id, card_id, destination_column_id, destination_position)
        return _build_board_payload(connection, board_id)


def _load_ordered_card_ids(connection: sqlite3.Connection, column_id: str) -> list[str]:
    rows = connection.execute(
        "SELECT id FROM cards WHERE column_id = ? ORDER BY position ASC",
        (column_id,),
    ).fetchall()
    return [row["id"] for row in rows]


def _reindex_column(
    connection: sqlite3.Connection,
    column_id: str,
    card_ids: list[str],
) -> None:
    for index, id_value in enumerate(card_ids):
        connection.execute(
            """
            UPDATE cards
            SET column_id = ?, position = ?, updated_at = datetime('now')
            WHERE id = ?
            """,
            (column_id, -(index + 1), id_value),
        )

    for index, id_value in enumerate(card_ids):
        connection.execute(
            """
            UPDATE cards
            SET column_id = ?, position = ?, updated_at = datetime('now')
            WHERE id = ?
            """,
            (column_id, index, id_value),
        )


def _get_or_create_thread_id(connection: sqlite3.Connection, board_id: str) -> int:
    row = connection.execute(
        """
        SELECT id
        FROM chat_threads
        WHERE board_id = ?
        ORDER BY id ASC
        LIMIT 1
        """,
        (board_id,),
    ).fetchone()
    if row is not None:
        return int(row["id"])

    result = connection.execute(
        """
        INSERT INTO chat_threads (board_id, title)
        VALUES (?, 'Main Chat')
        """,
        (board_id,),
    )
    return int(result.lastrowid)


def list_chat_messages_for_user(
    db_path: Path,
    username: str,
    limit: int = 30,
) -> list[dict[str, str]]:
    with _connect(db_path) as connection:
        board_id = _get_board_id(connection, username)
        thread_id = _get_or_create_thread_id(connection, board_id)
        rows = connection.execute(
            """
            SELECT role, content
            FROM chat_messages
            WHERE thread_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (thread_id, max(1, limit)),
        ).fetchall()

        messages = [{"role": row["role"], "content": row["content"]} for row in rows]
        messages.reverse()
        return messages


def list_chat_messages_for_board(
    db_path: Path,
    username: str,
    board_id: str,
    limit: int = 30,
) -> list[dict[str, str]]:
    with _connect(db_path) as connection:
        _validate_board_ownership(connection, username, board_id)
        thread_id = _get_or_create_thread_id(connection, board_id)
        rows = connection.execute(
            """
            SELECT role, content
            FROM chat_messages
            WHERE thread_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (thread_id, max(1, limit)),
        ).fetchall()

        messages = [{"role": row["role"], "content": row["content"]} for row in rows]
        messages.reverse()
        return messages


def append_chat_message_for_user(
    db_path: Path,
    username: str,
    role: str,
    content: str,
    metadata: dict | None = None,
) -> None:
    if role not in {"user", "assistant", "system"}:
        raise ValueError(f"Unsupported role: {role}")

    with _connect(db_path) as connection:
        board_id = _get_board_id(connection, username)
        thread_id = _get_or_create_thread_id(connection, board_id)
        connection.execute(
            """
            INSERT INTO chat_messages (thread_id, role, content, metadata_json)
            VALUES (?, ?, ?, ?)
            """,
            (thread_id, role, content, json.dumps(metadata or {})),
        )
        connection.execute(
            """
            UPDATE chat_threads
            SET updated_at = datetime('now')
            WHERE id = ?
            """,
            (thread_id,),
        )


def append_chat_message_for_board(
    db_path: Path,
    username: str,
    board_id: str,
    role: str,
    content: str,
    metadata: dict | None = None,
) -> None:
    if role not in {"user", "assistant", "system"}:
        raise ValueError(f"Unsupported role: {role}")

    with _connect(db_path) as connection:
        _validate_board_ownership(connection, username, board_id)
        thread_id = _get_or_create_thread_id(connection, board_id)
        connection.execute(
            """
            INSERT INTO chat_messages (thread_id, role, content, metadata_json)
            VALUES (?, ?, ?, ?)
            """,
            (thread_id, role, content, json.dumps(metadata or {})),
        )
        connection.execute(
            """
            UPDATE chat_threads
            SET updated_at = datetime('now')
            WHERE id = ?
            """,
            (thread_id,),
        )
