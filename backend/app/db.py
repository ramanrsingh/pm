import hashlib
import json
import secrets
import sqlite3
from pathlib import Path

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


class BoardNotFoundError(Exception):
    pass


class ColumnNotFoundError(Exception):
    pass


class CardNotFoundError(Exception):
    pass


def _connect(db_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON;")
    return connection


def _hash_password(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


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
              user_id INTEGER NOT NULL UNIQUE,
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
        _seed_mvp_user_data(connection)


def _seed_mvp_user_data(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        INSERT INTO users (username, password_hash)
        VALUES (?, ?)
        ON CONFLICT(username) DO NOTHING
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
        ON CONFLICT(user_id) DO NOTHING
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
        return row["password_hash"] == _hash_password(password)


def _get_board_id(connection: sqlite3.Connection, username: str) -> str:
    board_row = connection.execute(
        """
        SELECT b.id AS board_id
        FROM boards b
        INNER JOIN users u ON u.id = b.user_id
        WHERE u.username = ?
        """,
        (username,),
    ).fetchone()
    if board_row is None:
        raise BoardNotFoundError(f"Board not found for user: {username}")
    return str(board_row["board_id"])


def _build_board_payload(connection: sqlite3.Connection, board_id: str) -> dict:
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

    cards_by_column: dict[str, list[str]] = {str(column["id"]): [] for column in column_rows}
    cards: dict[str, dict] = {}

    for row in card_rows:
        card_id = str(row["id"])
        column_id = str(row["column_id"])
        cards_by_column.setdefault(column_id, []).append(card_id)
        cards[card_id] = {
            "id": card_id,
            "title": str(row["title"]),
            "details": str(row["details"]),
            "metadata": json.loads(str(row["metadata_json"])),
        }

    columns = [
        {
            "id": str(column["id"]),
            "title": str(column["title"]),
            "cardIds": cards_by_column.get(str(column["id"]), []),
        }
        for column in column_rows
    ]

    return {"columns": columns, "cards": cards}


def get_board_for_user(db_path: Path, username: str) -> dict:
    with _connect(db_path) as connection:
        board_id = _get_board_id(connection, username)
        return _build_board_payload(connection, board_id)


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


def create_card(db_path: Path, username: str, column_id: str, title: str, details: str) -> dict:
    with _connect(db_path) as connection:
        board_id = _get_board_id(connection, username)

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

        existing = connection.execute(
            "SELECT id FROM cards WHERE board_id = ? AND id = ?",
            (board_id, card_id),
        ).fetchone()
        if existing is None:
            raise CardNotFoundError(card_id)

        if title is None and details is None:
            return _build_board_payload(connection, board_id)

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


def _load_ordered_card_ids(connection: sqlite3.Connection, column_id: str) -> list[str]:
    rows = connection.execute(
        "SELECT id FROM cards WHERE column_id = ? ORDER BY position ASC",
        (column_id,),
    ).fetchall()
    return [str(row["id"]) for row in rows]


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


def move_card(
    db_path: Path,
    username: str,
    card_id: str,
    destination_column_id: str,
    destination_position: int | None,
) -> dict:
    with _connect(db_path) as connection:
        board_id = _get_board_id(connection, username)

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
            return _build_board_payload(connection, board_id)

        destination_ids = _load_ordered_card_ids(connection, destination_column_id)
        insert_position = len(destination_ids)
        if destination_position is not None:
            insert_position = max(0, min(destination_position, len(destination_ids)))
        destination_ids.insert(insert_position, card_id)

        # Move the card out of the source column first so source reindexing
        # does not collide with the card's previous (column_id, position).
        connection.execute(
            """
            UPDATE cards
            SET column_id = ?, position = -999999, updated_at = datetime('now')
            WHERE id = ?
            """,
            (destination_column_id, card_id),
        )

        _reindex_column(connection, source_column_id, source_ids)
        _reindex_column(connection, destination_column_id, destination_ids)

        return _build_board_payload(connection, board_id)


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

        messages = [{"role": str(row["role"]), "content": str(row["content"])} for row in rows]
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
