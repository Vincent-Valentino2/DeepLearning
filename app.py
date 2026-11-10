"""Vercel entrypoint for the FastAPI backend.

Vercel's Python runtime loads the top-level ``app`` from this file (project Root
Directory = repository root, so ``backend`` is importable as a package).
Locally and in Docker the backend still runs with ``uvicorn backend.main:app``.
"""
import os

# The Neon/Vercel Postgres integration provides DATABASE_URL; accept its other names too.
if not os.getenv("DATABASE_URL"):
    for name in ("POSTGRES_URL", "DATABASE_URL_UNPOOLED", "POSTGRES_URL_NON_POOLING"):
        if os.getenv(name):
            os.environ["DATABASE_URL"] = os.environ[name]
            break

# Neon may need a few seconds to wake from scale-to-zero; don't fall back to SQLite
# (the function filesystem is read-only) just because the first connect is slow.
os.environ.setdefault("DB_CONNECT_TIMEOUT", "15")

from backend.main import app  # noqa: E402,F401
