# Code Review

## Security (Medium)

- **Missing `secure=True` cookie flag** (`main.py` login endpoint) — should be set for HTTPS production
- **Hardcoded credentials** acceptable for MVP, but need a clear TODO before going to prod
- **AI prompt injection** — user input length is not bounded before sending to OpenRouter

## Code Quality (Medium)

- **Race condition in chat** (`KanbanBoard.tsx:148-174`) — input field should be disabled during submission, not just the button; prevents message-ordering issues on rapid sends
- **`response.board` not validated** before calling `setBoard()` — could set undefined state on malformed AI responses
- **Position bounds not validated** in `ai_workflow.py:_validate_move_payload` — negative or out-of-range positions accepted
- **Redundant `str()` casts** in `db.py` (lines 293, 321-326) — sqlite3.Row already returns proper types

## Standards Violations (Low)

- **Unstable `data-testid`** on chat messages (`KanbanBoard.tsx:312`): `chat-message-${index}` breaks if messages reorder. CLAUDE.md requires stable IDs.

## Test Coverage (Medium)

- No tests for `db.py` core functions (create_card, move_card, delete_card)
- No tests for `main.py` HTTP endpoints (auth flow, error responses)

## Architecture (Low)

- All board + chat state in one monolithic component — fine for MVP but will limit testability as it grows

## Minor

- `_REINDEX_PLACEHOLDER = -(10 ** 6)` in `db.py:80` — warrants a comment explaining why
- User message saved to chat history before AI operations complete — orphaned messages possible on failure

## What's Working Well

- AI parsing is resilient (tries multiple JSON extraction strategies)
- Drag-and-drop state management with `useMemo` is solid
- Error handling in `ai.py` does not leak the API key
- Bulk DB queries avoid N+1 patterns
