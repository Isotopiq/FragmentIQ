# AGENTS.md

## Cursor Cloud specific instructions

### Services overview

FragmentIQ is a self-hostable LC-MS/MS processing and annotation platform with two services:

| Service  | Stack                              | Dev command                                                          |
|----------|------------------------------------|----------------------------------------------------------------------|
| Backend  | FastAPI + SQLModel + SQLite        | `cd backend && . .venv/bin/activate && uvicorn app.main:app --reload` |
| Frontend | React + Vite + TypeScript + Tailwind v4 | `cd frontend && npm run dev`                                    |

Both run in mock mode by default (`MOCK_EXECUTION=true`). No Docker, Redis, or external tools are needed for local dev.

### Important gotchas

- **Tailwind CSS v4**: The frontend uses Tailwind v4 with the `@import "tailwindcss"` / `@config` syntax (NOT the v3 `@tailwind` directives). The `tailwind.config.cjs` is loaded via `@config` in `index.css`. Do not revert to v3 syntax.
- **flowbite-react**: Version 0.12.x does NOT export `flowbite-react/tailwind`. The CSS variables are loaded via `@import "flowbite-react/plugin/tailwindcss/index.css"` in `index.css`.
- **Backend startup seed**: `seed_demo_data()` runs on startup and calls `run_mock_job_sync()`, which uses a thread pool to avoid `asyncio.run()` inside uvicorn's running event loop. Do not simplify this back to a bare `asyncio.run()`.
- **Vite proxy**: The frontend Vite dev server proxies `/api` to `http://localhost:8000`, so both servers must be running for the frontend to work with live data.

### Standard commands

See `README.md` for full details. Quick reference:

- **Backend tests**: `PYTHONPATH=backend python3 -m pytest backend/tests -v`
- **Frontend tests**: `cd frontend && npx vitest run`
- **Frontend type-check**: `cd frontend && npx tsc --noEmit`
- **Frontend build**: `cd frontend && npm run build`
