# ===========================================================================
# Afterglow - Multi-stage Dockerfile
# ===========================================================================
# 사용법:
#   docker build --target backend -t afterglow-api .
#   docker build --target frontend -t afterglow .
#
# docker-compose에서는 build.target으로 자동 지정됩니다.
# ===========================================================================

# ─────────────────────────────────────────────────────────────────────────────
# Backend 스테이지
# ─────────────────────────────────────────────────────────────────────────────

# ── Backend 빌더 (gcc 컴파일용, 최종 이미지에 포함되지 않음) ─────────────────
FROM python:3.12-slim AS backend-builder

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libc6-dev \
    && rm -rf /var/lib/apt/lists/*

COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# ── Backend 프로덕션 (깨끗한 slim 이미지, gcc 없음) ──────────────────────────
FROM python:3.12-slim AS backend

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# 빌더에서 컴파일된 가상환경만 복사 (gcc/libc6-dev 제외)
COPY --from=backend-builder /app/.venv /app/.venv

COPY backend/pyproject.toml backend/uv.lock ./
COPY backend/app/ ./app/

RUN adduser --disabled-password --gecos "" appuser \
    && chown -R appuser:appuser /app

USER appuser

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# ── Backend 개발 스테이지 (docker-compose.override.yml에서 사용) ────────────
# 소스코드를 볼륨 마운트하여 실시간 반영, reload 모드로 실행
FROM backend-builder AS backend-dev
COPY backend/app/ ./app/
# dev 의존성(pytest 등) 설치
RUN uv sync --frozen --no-install-project
RUN adduser --disabled-password --gecos "" appuser \
    && chown -R appuser:appuser /app
USER appuser
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
# Frontend 개발 스테이지
# 볼륨 마운트 시 소스코드 실시간 반영, 아닐 경우 이미지 내 소스 사용
FROM oven/bun:1 AS frontend-dev

WORKDIR /app

COPY frontend/package.json frontend/bun.lock* ./
RUN bun install

COPY frontend/ .

EXPOSE 3000
ENV PORT=3000

CMD ["bun", "run", "dev", "--host", "0.0.0.0", "--port", "3000"]
