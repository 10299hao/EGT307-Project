FROM node:22-alpine AS frontend-builder
ARG PORTAL_VERSION=local-dev
ENV VITE_PORTAL_VERSION=$PORTAL_VERSION
WORKDIR /build/frontend
RUN corepack enable
COPY frontend/package.json frontend/pnpm-lock.yaml frontend/pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile
COPY frontend/ ./
RUN pnpm run build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORTAL_STATIC_DIR=/app/frontend/dist \
    PORTAL_DATABASE_PATH=/app/data/portal.db
WORKDIR /app
RUN addgroup --system portal && adduser --system --ingroup portal portal
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend/app ./backend/app
COPY --from=frontend-builder /build/frontend/dist ./frontend/dist
RUN mkdir -p /app/data && chown -R portal:portal /app
USER portal
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health/live')"
CMD ["uvicorn", "app.main:app", "--app-dir", "backend", "--host", "0.0.0.0", "--port", "8000"]
