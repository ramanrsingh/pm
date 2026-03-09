# Database Schema Proposal (Part 5)

This proposes the MVP SQLite schema for:
- users
- boards
- columns
- cards
- chat history

It is normalized, with JSON fields only for flexible metadata.

## Design Goals

- Keep writes and reads simple for MVP.
- Support current MVP constraint: one board per user.
- Keep schema extensible for future multi-board support.
- Preserve ordering for columns and cards.
- Keep flexible fields in JSON without denormalizing core entities.

## SQLite Notes

- Enable foreign keys on every connection: `PRAGMA foreign_keys = ON;`
- Suggested journaling for local reliability: `PRAGMA journal_mode = WAL;`

## Proposed Tables

```sql
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS boards (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL UNIQUE, -- MVP: exactly 1 board per user
  name TEXT NOT NULL DEFAULT 'Project Board',
  settings_json TEXT NOT NULL DEFAULT '{}', -- optional future board-level settings
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS board_columns (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  board_id INTEGER NOT NULL,
  key TEXT NOT NULL,               -- stable internal key (e.g. backlog, progress)
  title TEXT NOT NULL,             -- user-editable label
  position INTEGER NOT NULL,       -- 0-based order in board
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (board_id) REFERENCES boards(id) ON DELETE CASCADE,
  UNIQUE (board_id, key),
  UNIQUE (board_id, position)
);

CREATE TABLE IF NOT EXISTS cards (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  board_id INTEGER NOT NULL,
  column_id INTEGER NOT NULL,
  title TEXT NOT NULL,
  details TEXT NOT NULL DEFAULT '',
  position INTEGER NOT NULL,       -- 0-based order within the column
  metadata_json TEXT NOT NULL DEFAULT '{}', -- flexible card metadata
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (board_id) REFERENCES boards(id) ON DELETE CASCADE,
  FOREIGN KEY (column_id) REFERENCES board_columns(id) ON DELETE CASCADE,
  UNIQUE (column_id, position)
);

CREATE TABLE IF NOT EXISTS chat_threads (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  board_id INTEGER NOT NULL,       -- MVP: one thread per board is enough, but table allows expansion
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
  metadata_json TEXT NOT NULL DEFAULT '{}', -- token usage, model info, parse diagnostics, etc.
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (thread_id) REFERENCES chat_threads(id) ON DELETE CASCADE
);
```

## Indexes

```sql
CREATE INDEX IF NOT EXISTS idx_boards_user_id ON boards(user_id);
CREATE INDEX IF NOT EXISTS idx_columns_board_id_position ON board_columns(board_id, position);
CREATE INDEX IF NOT EXISTS idx_cards_board_id ON cards(board_id);
CREATE INDEX IF NOT EXISTS idx_cards_column_id_position ON cards(column_id, position);
CREATE INDEX IF NOT EXISTS idx_threads_board_id ON chat_threads(board_id);
CREATE INDEX IF NOT EXISTS idx_messages_thread_id_created_at ON chat_messages(thread_id, created_at);
```

## Mapping to Frontend Board Shape

Current frontend model:
- `columns[]` with ordered columns and card IDs
- `cards{}` keyed by card ID

Backend read flow:
1. Load board by `user_id`.
2. Load columns ordered by `position`.
3. Load cards ordered by `(column_id, position)`.
4. Materialize response JSON:
   - `columns[i].cardIds` from ordered cards per column
   - `cards` object keyed as string IDs (or prefixed IDs if desired)

## JSON Fields Policy

- `boards.settings_json`: optional board UI options (future).
- `cards.metadata_json`: flexible card data (labels, estimates, custom flags, due dates).
- `chat_messages.metadata_json`: model/provider diagnostics and structured parse data.

Core querying fields remain normalized columns; JSON is not required for main board reads.

## Bootstrap and Migration Strategy

Use simple SQL-file migrations with a schema version table:

```sql
CREATE TABLE IF NOT EXISTS schema_migrations (
  version INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  applied_at TEXT NOT NULL DEFAULT (datetime('now'))
);
```

Startup behavior:
1. Open SQLite DB path (create file if missing).
2. Enable pragmas (`foreign_keys`, optional `journal_mode=WAL`).
3. Run unapplied migrations in order.
4. If no users exist in MVP, seed user row for `user` account and seed one board + fixed columns.

This is enough for MVP and avoids heavy migration frameworks.

## Test Plan (for Part 6 implementation)

- Schema integrity test:
  - all tables exist
  - foreign keys enabled
  - unique constraints enforced
  - indexes present
- JSON serialization tests:
  - `metadata_json` round-trip for cards/messages
  - invalid JSON inputs rejected or normalized before insert
- Relational behavior tests:
  - deleting board cascades columns/cards/threads/messages
  - column/card positions remain unique within scope

## Open Decisions (Recommended Defaults)

- Card ID external format:
  - Recommended: expose numeric IDs as strings to frontend for minimal mapping.
- `password_hash` for MVP fixed login:
  - Recommended: still store hashed password in DB for forward compatibility.
- Chat threads per board:
  - Recommended: one active thread in MVP, table remains extensible.
