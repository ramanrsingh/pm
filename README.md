# Project Management MVP

## Run

### Docker Compose

```bash
docker compose up --build
```

App URL: `http://127.0.0.1:8000`

- `/` serves the built Next.js frontend (static export) through FastAPI.
- `/api/health` serves backend health JSON.
- Login credentials for MVP: `user` / `password`.

### Scripts

- Linux: `scripts/start-linux.sh`, `scripts/stop-linux.sh`
- macOS: `scripts/start-mac.sh`, `scripts/stop-mac.sh`
- Windows PowerShell: `scripts/start-windows.ps1`, `scripts/stop-windows.ps1`
- Windows CMD: `scripts/start-windows.bat`, `scripts/stop-windows.bat`

## Backend Test

```bash
cd backend
uv sync --dev
uv run pytest
```
