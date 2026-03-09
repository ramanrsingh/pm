# Frontend Agent Notes

This file describes the existing frontend demo in `frontend/` and how to work on it safely.

## Stack

- Next.js App Router (`next` 16)
- React 19 + TypeScript
- Tailwind CSS v4 (single global stylesheet)
- Drag and drop via `@dnd-kit`
- Unit tests: Vitest + Testing Library
- E2E tests: Playwright

## Current App Behavior

- Entry page is `src/app/page.tsx` and renders `KanbanBoard` only.
- The board loads and persists through backend API routes.
- Fixed 5-column Kanban layout with:
  - inline column title rename
  - add card form per column
  - delete card action
  - drag and drop card movement across/within columns

## Source Map

- `src/components/KanbanBoard.tsx`: board state orchestration, API load/mutations, drag/drop handlers.
- `src/lib/api.ts`: frontend API client for board endpoints.
- `src/components/KanbanColumn.tsx`: column UI, rename input, card list, add-card form.
- `src/components/KanbanCard.tsx`: sortable card UI and delete action.
- `src/components/NewCardForm.tsx`: local add-card form state.
- `src/lib/kanban.ts`: board types, seeded `initialData`, `moveCard`, and `createId`.

## Styling and Design Rules

- Global tokens in `src/app/globals.css` define project palette:
  - `--accent-yellow: #ecad0a`
  - `--primary-blue: #209dd7`
  - `--secondary-purple: #753991`
  - `--navy-dark: #032147`
  - `--gray-text: #888888`
- Fonts are loaded in `src/app/layout.tsx` (`Space Grotesk` display, `Manrope` body).
- Existing visual direction should be preserved unless explicitly requested.

## Test Baseline

- Unit tests:
  - `src/lib/kanban.test.ts`
  - `src/components/KanbanBoard.test.tsx`
- E2E tests:
  - `tests/kanban.spec.ts`
- Common commands:
  - `npm run dev`
  - `npm run test:unit`
  - `npm run test:e2e`
  - `npm run test:all`

## Frontend Working Conventions

- Keep components small and directly tied to current behavior.
- Prefer updating `src/lib/kanban.ts` logic first for board behavior changes, then wire UI.
- Keep `data-testid` attributes stable where tests depend on them (`column-*`, `card-*`).
- For stateful UI behavior, add/adjust unit tests in `src/**/*.test.ts(x)`.
- For user workflows (render, add card, move card), maintain Playwright coverage in `tests/`.

## Near-Term Integration Notes

- Keep board domain types centralized to simplify future API typing.
