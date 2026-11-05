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

EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8001/api/health || exit 1

CMD ["python", "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8001"]
