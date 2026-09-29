# syntax=docker/dockerfile:1

# ---------- Stage 1: build frontend ----------
FROM node:20-alpine AS frontend-build
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci || npm install
COPY frontend/ ./
RUN npm run build

# ---------- Stage 2: backend runtime ----------
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# System deps for Playwright chromium + xvfb (headful automation in a container)
RUN apt-get update && apt-get install -y --no-install-recommends \
        xvfb \
        xauth \
        libx11-xcb1 \
        libxcb-dri3-0 \
        libnss3 \
        libnspr4 \
        libdbus-1-3 \
        libatk1.0-0 \
        libatk-bridge2.0-0 \
        libcups2 \
        libxcomposite1 \
        libxdamage1 \
        libxrandr2 \
        libgbm1 \
        libasound2 \
        libpango-1.0-0 \
        libcairo2 \
        libatspi2.0-0 \
        libxkbcommon0 \
        libxfixes3 \
        libxext6 \
        libglib2.0-0 \
        libdrm2 \
        libexpat1 \
        libxcb1 \
        fonts-noto \
        fonts-dejavu-core \
        fonts-unifont \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && playwright install chromium \
    && rm -rf /root/.cache/ms-playwright/*.zip /tmp/*

COPY backend/app ./app
COPY backend/tests ./tests
COPY --from=frontend-build /build/frontend/dist /frontend/dist

# Data + generated files (SQLite db, encryption key, printed output)
RUN mkdir -p /app/data /app/app/print_output
VOLUME ["/app/data", "/app/app/print_output"]

ENV MANDI_DATABASE_URL=sqlite+aiosqlite:////app/data/mandi.db
ENV MANDI_API_HOST=0.0.0.0
ENV MANDI_API_PORT=8000

EXPOSE 8000

# Run uvicorn under Xvfb so Playwright can launch headful chromium.
CMD ["sh", "-c", "xvfb-run -a uvicorn app.main:app --host ${MANDI_API_HOST:-0.0.0.0} --port ${MANDI_API_PORT:-8000}"]
