# ===========================================================================
# Union - Multi-stage Dockerfile
# ===========================================================================
# 사용법:
#   docker build --target backend -t union-backend .
#   docker build --target frontend -t union-frontend .
#
# docker-compose에서는 build.target으로 자동 지정됩니다.
# ===========================================================================

# ─────────────────────────────────────────────────────────────────────────────
# Backend 스테이지
# ─────────────────────────────────────────────────────────────────────────────

FROM python:3.12-slim AS backend-base

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libc6-dev \
    && rm -rf /var/lib/apt/lists/* \
    && adduser --disabled-password --gecos "" appuser

COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY backend/app/ ./app/
RUN chown -R appuser:appuser /app

USER appuser

FROM backend-base AS backend
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# ── Backend 개발 스테이지 (docker-compose.override.yml에서 사용) ────────────
# 소스코드를 볼륨 마운트하여 실시간 반영, reload 모드로 실행
FROM backend-base AS backend-dev
# dev 의존성(python-dotenv 등) 설치
RUN uv sync --frozen --no-install-project
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# ─────────────────────────────────────────────────────────────────────────────
# Frontend 스테이지
# ─────────────────────────────────────────────────────────────────────────────

FROM oven/bun:1 AS frontend-builder

WORKDIR /app

COPY frontend/package.json frontend/bun.lock* ./
RUN bun install --frozen-lockfile

COPY frontend/ .
RUN bun run build

FROM node:20-alpine AS frontend

WORKDIR /app

COPY --from=frontend-builder /app/build ./build
COPY --from=frontend-builder /app/package.json ./

RUN npm install --omit=dev --ignore-scripts \
    && adduser -D appuser \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 3000
ENV PORT=3000

CMD ["node", "build"]

# ── Frontend 개발 스테이지 (docker-compose.override.yml에서 사용) ────────────
# 소스코드를 볼륨 마운트하여 실시간 반영, Vite dev 서버로 HMR 지원
FROM oven/bun:1 AS frontend-dev

WORKDIR /app

COPY frontend/package.json frontend/bun.lock* ./
RUN bun install

EXPOSE 3000
ENV PORT=3000

CMD ["bun", "run", "dev", "--host", "0.0.0.0", "--port", "3000"]
