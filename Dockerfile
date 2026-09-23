# ── Stage 1: Build Frontend ──────────────────────────────────────────────────
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# ── Stage 2: Production Python Runner ────────────────────────────────────────
FROM python:3.12-slim AS runner
WORKDIR /app

# Install curl for container health checks
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

# Install Python backend dependencies
COPY backend/requirements.txt ./backend/
RUN pip install --no-cache-dir -r backend/requirements.txt

# Copy backend source code
COPY backend/ ./backend/

# Copy built frontend assets from builder stage
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Create persistent storage directory for SQLite
RUN mkdir -p /data

# Default environment variables for production
ENV DATABASE_URL="sqlite:////data/app.db" \
    FRONTEND_DIST_DIR="/app/frontend/dist" \
    BACKEND_HOST="0.0.0.0" \
    BACKEND_PORT="8000" \
    COOKIE_SECURE="true" \
    COOKIE_SAME_SITE="lax"

EXPOSE 8000

# Health check using the FastAPI /health endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# Start FastAPI application via Uvicorn
CMD ["uvicorn", "app.main:app", "--app-dir", "backend", "--host", "0.0.0.0", "--port", "8000"]
