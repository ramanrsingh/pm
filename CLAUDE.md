# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Project Management MVP: a Kanban board web app with AI-assisted task management. FastAPI backend serves both the API and the statically exported Next.js frontend. Everything runs in a single Docker container.

- Login credentials (hardcoded MVP): `user` / `password`
- App runs at `http://127.0.0.1:8000`
- AI model: `openai/gpt-oss-120b:free` via OpenRouter (`OPENROUTER_API_KEY` in `.env`)

## Commands

### Docker (full stack)
```bash
docker compose up --build
```

### Frontend (Next.js in `frontend/`)
```bash
npm run dev           # Dev server on port 3000
npm run build         # Production static export
npm run lint          # ESLint
npm run test:unit     # Vitest unit tests
npm run test:unit:watch
npm run test:e2e      # Playwright E2E tests (requires running server)
npm run test:all      # All tests
```

### Backend (Python in `backend/`)
```bash
uv sync --dev         # Install dependencies
uv run pytest         # Run all tests
uv run pytest tests/test_foo.py::test_bar  # Run a single test
```

## Architecture

The Dockerfile builds the Next.js static export, then copies it into the Python image. FastAPI serves the static files at `/` and all API routes under `/api/`.

**Backend (`backend/app/`):**
- `main.py` — FastAPI app, all route handlers
- `db.py` — SQLite init and query helpers (auto-creates DB on startup)
- `ai.py` — OpenRouter API client
- `ai_workflow.py` — AI response parsing and board update logic

**Frontend (`frontend/src/`):**
- `components/KanbanBoard.tsx` — Board state, API calls, drag-and-drop orchestration
- `components/ChatSidebar.tsx` — AI chat interface
- `lib/api.ts` — Typed API client used by all components
- `lib/kanban.ts` — Board types (`Board`, `Column`, `Card`), `moveCard`, `createId`
- `app/globals.css` — CSS custom properties for the color palette

**Database:** SQLite, tables: `users`, `boards`, `columns`, `cards`, `chat_threads`, `chat_messages`

**API routes:**
- `POST /api/auth/login` | `POST /api/auth/logout` | `GET /api/auth/me`
- `GET /api/board`
- `PATCH /api/columns/{column_id}`
- `POST /api/cards` | `PATCH /api/cards/{card_id}` | `DELETE /api/cards/{card_id}` | `POST /api/cards/{card_id}/move`
- `POST /api/chat` (AI)

## Coding Standards

- Keep it simple — no over-engineering, no unnecessary defensive programming, no extra features.
- When hitting issues, identify root cause before attempting a fix. Prove with evidence.
- No emojis anywhere in the codebase or docs.
- Keep `data-testid` attributes stable (`column-*`, `card-*`) — Playwright tests depend on them.
- Board domain types live in `src/lib/kanban.ts`; update logic there first, then wire UI.

## Color Palette

Defined as CSS vars in `globals.css` and used throughout:
- `--accent-yellow: #ecad0a`
- `--primary-blue: #209dd7`
- `--secondary-purple: #753991`
- `--navy-dark: #032147`
- `--gray-text: #888888`

Fonts: `Space Grotesk` (display), `Manrope` (body), loaded in `src/app/layout.tsx`.
