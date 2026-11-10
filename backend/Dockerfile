# Dockerfile for FastAPI + Scikit-Learn Backend
FROM python:3.12-slim

WORKDIR /app

# Install system dependencies if needed (e.g. gcc for c extensions)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r ./backend/requirements.txt

# Copy application files
COPY backend ./backend
COPY data/sample_movies.json ./data/sample_movies.json

# Release metadata reported by GET /api/health
ARG GIT_COMMIT_SHA=unknown
ARG RELEASE_ENV=production
ENV GIT_COMMIT_SHA=$GIT_COMMIT_SHA \
    RELEASE_ENV=$RELEASE_ENV

EXPOSE 8001

# PORT defaults to 8001 (docker compose); a cloud host may inject its own PORT
ENV PORT=8001

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:${PORT}/api/health || exit 1

CMD ["sh", "-c", "exec python -m uvicorn backend.main:app --host 0.0.0.0 --port ${PORT}"]
