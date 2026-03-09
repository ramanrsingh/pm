# Code Review

All items below were addressed in the same session. Status column indicates disposition.



Reviewed against the full source tree as of the current commit.

---

## Summary

| Severity | Count | Status |
|----------|-------|--------|
| High     | 3     | Fixed  |
| Medium   | 7     | Fixed (M5 deferred post-MVP) |
| Low      | 6     | Fixed  |

---

## High

### H1 — Cookie stores raw username; authentication is forgeable

**File:** `backend/app/main.py:110-116`, `main.py:78-84`

The `pm_auth` cookie is set to `payload.username` (the literal string `"user"`). `_require_username` reads that cookie value and uses it directly as the authenticated username, with no signature or token verification. Any client that sets `pm_auth=user` in a request header bypasses the login flow entirely.

**Fix:** Replace the cookie value with an opaque session token (e.g. `secrets.token_hex(32)`) stored server-side against the username. Look up the username from the token on each request.

---

### H2 — Passwords hashed with unsalted SHA-256

**File:** `backend/app/db.py:97-98`

```python
def _hash_password(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
```

SHA-256 without a per-user salt is vulnerable to rainbow table and precomputed hash attacks. If the database file is ever exposed, the password is trivially recoverable against any common password list.

**Fix:** Use `hashlib.scrypt` or the `bcrypt`/`argon2-cffi` package with a random per-user salt. Minimum change: add `salt = secrets.token_bytes(16)` and store it alongside the hash.

---

### H3 — Redundant double credential check in login

**File:** `backend/app/main.py:98-108`

The login endpoint does two independent checks:

1. Hardcoded constant comparison (`MVP_USERNAME`, `MVP_PASSWORD`) — lines 98-99
2. `verify_credentials` DB lookup — lines 104-108

These are always in sync right now, but the hardcoded check runs first and short-circuits. If the DB user is ever updated (different password, additional users), the constant check will block valid users before the DB check even runs. The two checks encode contradictory policies and will diverge.

**Fix:** Remove the hardcoded constant check (lines 98-102) and rely solely on `verify_credentials`. The constant check adds no safety and creates a maintenance trap.

---

## Medium

### M1 — Empty or whitespace-only column title accepted

**File:** `backend/app/main.py:45-46`, `db.py:328-341`

`RenameColumnPayload.title` has no `min_length` or `strip_whitespace` constraint. The rename call passes `payload.title` directly to `db.rename_column` without stripping. A client can rename a column to `""` or `"   "`.

**Fix:** Add Pydantic field constraints:
```python
class RenameColumnPayload(BaseModel):
    title: str = Field(min_length=1, strip_whitespace=True)
```

---

### M2 — Whitespace-only card title collapses to empty string on insert

**File:** `backend/app/main.py:167`

`payload.title.strip()` is called at the call site, so a title like `"   "` becomes `""` and is inserted into the DB. The `cards.title` column has no NOT NULL constraint beyond the schema default, so an empty string is silently accepted.

**Fix:** Add a `min_length=1` constraint to `CreateCardPayload.title` in Pydantic (before stripping), or raise a 422 when the stripped value is empty.

---

### M3 — Magic number -999999 in move_card

**File:** `backend/app/db.py:514`

```python
SET column_id = ?, position = -999999
```

This sentinel value is used to temporarily park a card outside valid position space while source and destination columns are reindexed, working around the `UNIQUE(column_id, position)` constraint. The intent is not obvious from the number alone.

**Fix:** Define a module-level constant:
```python
_REINDEX_PLACEHOLDER = -(10 ** 6)
```
and reference it in the query.

---

### M4 — `initialData` exported from library module, only used in tests

**File:** `frontend/src/lib/kanban.ts:18-72`

The 60-line `initialData` constant is exported from the library module but is only imported in `KanbanBoard.test.tsx` as test fixture data. The application itself loads board state entirely from the API. Exporting test fixture data from a production module is confusing and inflates the bundle.

**Fix:** Move `initialData` into the test file (`KanbanBoard.test.tsx`) or a dedicated `src/test/fixtures.ts` file and remove the export from `kanban.ts`.

---

### M5 — Entire conversation sent as a single user message

**File:** `backend/app/ai.py:54-56`, `ai_workflow.py:17-31`

`build_ai_prompt` serialises the board snapshot, full chat history, and the new user message into one JSON blob, which is sent as a single `{"role": "user", ...}` entry. The model therefore sees the entire conversation as one turn. Chat history is present as data inside the payload, not as actual conversation turns, so the model cannot use its conversational instruction-following capability effectively.

**Fix (post-MVP):** Send `chatHistory` entries as alternating `user`/`assistant` messages in the `messages` array, with the board snapshot and instructions as a `system` message.

---

### M6 — `apply_ai_operations` makes redundant per-operation DB round-trips

**File:** `backend/app/ai_workflow.py:193-228`

Each call to `create_card`, `update_card`, and `move_card` opens a DB connection and rebuilds the full board payload (which involves two queries), but `apply_ai_operations` ignores all those return values and calls `get_board_for_user` again at the end. For N operations this is 2N+2 queries where 2 would suffice.

**Fix:** The inner `db.*` functions could have a thin variant that performs the mutation without rebuilding the board payload, or `apply_ai_operations` could accumulate operations and apply them in a single transaction. For current scale this is negligible but it will compound.

---

### M7 — No test for forged cookie / unauthenticated access via cookie manipulation

**File:** `backend/tests/`

Because the cookie value is the raw username (H1), a forged cookie is the primary attack vector. There is no test that sends a manually crafted `pm_auth` cookie and verifies the application's response. If H1 is fixed (session tokens), coverage for invalid/expired tokens is also needed.

**Add tests:**
- `test_forged_auth_cookie_rejected` — sends a request with `pm_auth=user` without going through `/api/auth/login`
- After H1 fix: `test_expired_token_rejected`, `test_unknown_token_rejected`

---

## Low

### L1 — `createId` is dead code

**File:** `frontend/src/lib/kanban.ts:164-168`

`createId` is exported but never imported or called anywhere in the application or tests. The backend generates all card IDs.

**Fix:** Delete the function.

---

### L2 — Missing type annotation on `db_path` in `apply_ai_operations`

**File:** `backend/app/ai_workflow.py:182-186`

```python
def apply_ai_operations(
    db_path,          # no type hint
    username: str,
    ...
```

All other db-layer functions annotate `db_path: Path`. This inconsistency reduces IDE support and static analysis coverage.

**Fix:** Add `db_path: Path` and import `Path` from `pathlib`.

---

### L3 — No test for empty title on rename or create

**File:** `backend/tests/test_board_api.py`

There are no tests for:
- `PATCH /api/columns/{id}` with `{"title": ""}` or `{"title": "   "}`
- `POST /api/cards` with a whitespace-only title

These are the same cases as M1 and M2. Tests should be added alongside the validation fix so they do not regress.

---

### L4 — No test for moving a card to a non-existent column

**File:** `backend/tests/test_board_api.py`

`db.move_card` raises `ColumnNotFoundError` when the destination column does not belong to the board. This is a distinct code path from the card-not-found path and is not covered by any existing test.

**Add test:** `test_move_card_to_missing_column_returns_404`

---

### L5 — No test for partial AI operation failure

**File:** `backend/tests/test_app.py`

`apply_ai_operations` accumulates errors and continues applying valid operations when earlier ones fail. The mixed success/failure path is not tested. A regression here would silently drop valid operations or emit incomplete `operationErrors` lists.

**Add test:** provide a batch with one valid `create_card` and one invalid `edit_card` (non-existent card ID); assert the valid operation was applied and the error list contains exactly one entry.

---

### L6 — `model` field returned by AI endpoint but absent from frontend type

**File:** `frontend/src/lib/api.ts:23-34`, `backend/app/main.py:272`

The backend returns `"model": OPENROUTER_MODEL` in the AI chat response. `AIChatApiResponse` in the frontend does not declare this field, so it is silently discarded. This is not currently a bug, but if the field is ever needed (e.g. to display which model responded), the type will need updating.

**Fix:** Either remove the `model` field from the backend response if it is not consumed, or add `model: string` to `AIChatApiResponse`.

---

## Positive observations

- All SQL queries use parameterised statements throughout `db.py`. No SQL injection risk.
- `_reindex_column` correctly uses a two-pass approach (negative positions first) to avoid colliding with the `UNIQUE(column_id, position)` constraint during in-place reordering.
- `parse_ai_output` degrades gracefully: invalid or unparseable model output returns the raw text without corrupting board state.
- Playwright E2E tests mock all API routes and are self-contained; they do not require a live backend.
- Error types (`BoardNotFoundError`, `ColumnNotFoundError`, `CardNotFoundError`) give clean, typed error handling at the API layer.
