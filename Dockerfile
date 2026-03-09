FROM node:22-alpine AS frontend-builder

WORKDIR /app/frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend ./
RUN npm run build

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FRONTEND_DIST=/app/frontend-out \
    DB_PATH=/app/data/pm.db

WORKDIR /app/backend

RUN pip install --no-cache-dir uv

COPY backend/pyproject.toml ./pyproject.toml
RUN uv sync --no-dev

COPY backend /app/backend
COPY --from=frontend-builder /app/frontend/out /app/frontend-out

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
