# Project Management MVP Execution Plan

This document is the working checklist for Parts 1-10. Keep it updated as work progresses.

## Global Constraints and Quality Gates

- [ ] Keep implementation simple and MVP-scoped only.
- [ ] Use latest stable, idiomatic libraries as of implementation date.
- [ ] Root-cause-first debugging: capture evidence before each fix.
- [ ] Respect color scheme and existing frontend visual direction unless explicitly changed.
- [ ] Backend work must follow both root `AGENTS.md` and `backend/AGENTS.md`.
- [ ] Target around 80% unit test coverage for meaningful project code when sensible; do not add low-value tests only to chase a number.
- [ ] Integration tests must cover core user flows end-to-end, including auth, board persistence, and AI-assisted board updates.

## Part 1: Planning and Project Docs

### Checklist
- [x] Convert this file into detailed actionable checklists for Parts 1-10.
- [x] Define tests and success criteria for every part.
- [x] Create `frontend/AGENTS.md` describing existing frontend structure and conventions.
- [x] Review plan with user and get explicit approval before Part 2.

### Tests
- [x] Manual review: all parts include implementation checklist + tests + success criteria.
- [x] Manual review: plan reflects clarified decisions:
  - backend instructions are mandatory when backend work starts
  - 80% minimum unit coverage
  - best-effort structured output parsing for MVP
  - normalized DB tables with JSON fields for metadata

### Success Criteria
- [x] User explicitly approves this enriched plan.
- [x] `frontend/AGENTS.md` exists and accurately documents current frontend demo.

## Part 2: Scaffolding (Docker + FastAPI Hello World)

### Checklist
- [x] Create backend app skeleton in `backend/` with FastAPI entrypoint.
- [x] Add Dockerfile and related container config at project root.
- [x] Configure Python dependency management with `uv` inside container flow.
- [x] Add start/stop scripts for macOS, Linux, Windows under `scripts/`.
- [x] Serve simple static hello-world page from `/` via FastAPI.
- [x] Add one example API route (for example `/api/health`) and wire hello-world page to call it.
- [x] Document local run flow briefly in README.

### Tests
- [x] Backend unit tests for app startup and `/api/health` route.
- [x] Integration test: running container serves `/` and API response successfully.
- [x] Script validation: each OS script starts and stops services successfully (or documented platform-specific fallback if not executable in current environment).

### Success Criteria
- [x] `docker build` and `docker run` work locally.
- [x] Visiting `/` shows hello-world page served by FastAPI.
- [x] API call from page to backend route succeeds.

## Part 3: Add Frontend Static Build + Serve at `/`

### Checklist
- [x] Integrate existing Next.js frontend into containerized stack.
- [x] Configure frontend static build output.
- [x] Configure FastAPI to serve built static frontend at `/`.
- [x] Ensure current Kanban demo behavior remains intact.
- [x] Update scripts for build/start with frontend artifact generation.

### Tests
- [x] Frontend unit tests pass.
- [x] Integration test: built app served by backend renders Kanban board at `/`.
- [x] Integration test: drag/drop flow works in served build (not only dev mode).
- [ ] Coverage is reviewed and remains at a sensible level (target ~80% where meaningful).

### Success Criteria
- [x] Single container serves the real frontend demo from backend.
- [x] No regression in existing board interactions.

## Part 4: Fake Sign-In/Sign-Out Flow

### Checklist
- [x] Add sign-in screen gate at `/`.
- [x] Implement MVP credentials check (`user` / `password`).
- [x] Create session mechanism suitable for local MVP (cookie or token).
- [x] Require authenticated session before showing board.
- [x] Add logout action that clears session and returns to sign-in screen.

### Tests
- [x] Backend unit tests for auth validation and session checks.
- [x] Frontend unit tests for login form behavior and error states.
- [x] Integration tests for login success, login failure, protected route behavior, and logout.
- [ ] Coverage is reviewed for changed code and improved where gaps are meaningful.

### Success Criteria
- [x] Board is inaccessible without login.
- [x] Correct credentials allow access.
- [x] Logout reliably ends session.

## Part 5: Database Modeling (Design + Sign-Off)

### Checklist
- [x] Propose normalized SQLite schema for users, boards, columns, cards, and chat history.
- [x] Include JSON fields for flexible card metadata (and other flexible payloads only where needed).
- [x] Define indices and foreign keys for core queries.
- [x] Document migration/bootstrap behavior for creating DB when absent.
- [x] Write schema/design doc in `docs/` and request user sign-off.

### Tests
- [ ] Schema validation script/test confirms tables, constraints, and indexes exist.
- [ ] Unit tests for serialization/deserialization of JSON metadata fields.

### Success Criteria
- [x] User approves documented schema.
- [x] Schema supports one-board-per-user MVP while allowing future multi-user extension.

## Part 6: Backend CRUD APIs + DB Initialization

### Checklist
- [x] Implement DB initialization on startup if DB file does not exist.
- [x] Add API routes to read board for authenticated user.
- [x] Add API routes to rename columns.
- [x] Add API routes to create/edit/delete/move cards.
- [x] Ensure all board changes persist in SQLite.
- [x] Keep API contracts explicit and minimal.

### Tests
- [x] Backend unit tests for service/repository logic and validation.
- [x] Integration tests for all board CRUD/move endpoints against test DB.
- [x] Auth integration tests to ensure user isolation.
- [ ] Coverage is reviewed for backend changes and improved where meaningful.

### Success Criteria
- [x] API fully supports board operations required by frontend.
- [x] DB created automatically when missing.
- [x] Data remains persistent across restarts.

## Part 7: Frontend + Backend Integration (Persistent Board)

### Checklist
- [x] Replace frontend in-memory board state bootstrapping with backend-loaded state.
- [x] Wire all card/column actions to backend APIs.
- [x] Add loading and error handling for API operations.
- [x] Keep drag/drop UX responsive and consistent.
- [x] Fix cross-column move persistence bug caused by SQLite unique-position conflicts.

### Tests
- [x] Frontend unit tests for API client and state update behavior.
- [x] Integration tests for full user board lifecycle: login, load, edit, move, refresh persistence.
- [x] End-to-end tests for failure handling (API error surfaced clearly).
- [ ] Coverage is reviewed for frontend changes and improved where meaningful.

### Success Criteria
- [x] Board state persists between sessions/page refreshes.
- [x] UI and database remain consistent after each mutation.

## Part 8: OpenRouter Connectivity

### Checklist
- [x] Add backend AI client configured for OpenRouter using `.env` key.
- [x] Use model `openai/gpt-oss-120b:free`.
- [x] Add minimal backend endpoint to execute a simple AI prompt.
- [x] Implement basic error handling for missing key, timeout, and provider errors.

### Tests
- [x] Unit tests mocking OpenRouter client behavior.
- [x] Integration smoke test invoking AI endpoint with prompt `2+2`.
- [x] Manual verification in local run that endpoint returns valid response payload.

### Success Criteria
- [x] AI endpoint can successfully call OpenRouter from backend.
- [x] Failure modes return clear, non-crashing error responses.

## Part 9: Structured AI Response With Optional Board Update

### Checklist
- [x] Define structured response contract for assistant message + optional board operations.
- [x] Send board JSON snapshot + user message + chat history to AI on each chat request.
- [x] Implement best-effort parsing for model output (MVP):
  - try strict parse first
  - fallback parse/coerce if possible
  - if unparseable, return assistant text without board mutation
- [x] Validate and apply allowed board updates server-side before persisting.

### Tests
- [x] Unit tests for parser across valid, partially valid, and invalid outputs.
- [x] Unit tests for update-application logic (create/edit/move operations).
- [x] Integration tests ensuring valid AI update mutates DB and invalid update does not corrupt state.
- [ ] Coverage is reviewed for new backend modules and improved where meaningful.

### Success Criteria
- [x] Chat endpoint reliably returns assistant text.
- [x] Optional board updates are safely applied when parseable and valid.
- [x] Invalid model output degrades gracefully without data loss.

## Part 10: Frontend AI Sidebar + Auto Refresh

### Checklist
- [x] Build sidebar chat UI integrated into existing board layout.
- [x] Support chat history rendering and user input submission.
- [x] Call backend AI endpoint and render assistant responses.
- [x] When backend indicates board update, refresh board state automatically.
- [x] Ensure responsive behavior on desktop and mobile.

### Tests
- [x] Frontend unit tests for chat widget state handling.
- [x] Integration tests for message send/receive and board auto-refresh after AI update.
- [x] End-to-end tests covering complete workflow: login -> board -> AI instruction -> board changes visible.
- [ ] Coverage is reviewed for frontend modules added/changed and improved where meaningful.

### Success Criteria
- [x] Sidebar chat works end-to-end with backend AI service.
- [x] AI-driven board updates appear in UI without manual reload.
- [x] Core flows remain stable under normal usage.

## Definition of Done (Project)

- [ ] Parts 1-10 completed and checked.
- [ ] Coverage quality is acceptable for MVP scope, with ~80% as a guideline rather than a forced threshold.
- [ ] Robust integration/e2e tests cover core business flows.
- [ ] Local Docker workflow starts cleanly and runs the full app.
- [ ] README remains concise and accurate.
