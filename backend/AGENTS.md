# Backend

FastAPI backend for the Project Management MVP.

## Current Scope (Part 6)

- Serves built Next.js static export from `GET /`
- Provides API health endpoint at `GET /api/health`
- Provides MVP auth endpoints:
  - `POST /api/auth/login`
  - `POST /api/auth/logout`
  - `GET /api/auth/me`
- Provides SQLite-backed board APIs:
  - `GET /api/board`
  - `PATCH /api/columns/{column_id}`
  - `POST /api/cards`
  - `PATCH /api/cards/{card_id}`
  - `DELETE /api/cards/{card_id}`
  - `POST /api/cards/{card_id}/move`
- Runs in Docker using `uv` for Python dependency management

## Next Planned Scope

- Add AI routes via OpenRouter
