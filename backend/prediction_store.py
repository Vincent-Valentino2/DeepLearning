"""
Prediction log storage & analytics aggregation.

Used by:
  * POST /api/predict and POST /api/compare  -> log every MLP inference
  * GET  /api/analytics/summary              -> aggregated platform insights

Storage strategy
----------------
* If ``DATABASE_URL`` is set (docker-compose provides it) and PostgreSQL is
  reachable, rows go to the ``prediction_logs`` table defined in db/init.sql.
* Otherwise (local dev without Docker, CI) it falls back to a SQLite file
  ``data/prediction_logs.db`` so the endpoints keep working.

The backend is chosen lazily on first use, so ``import backend.main`` never
touches a database (important for the CI import check).

Logging is best-effort: a storage failure must never break a prediction.
"""
import os
import sqlite3
import logging
import threading
import time
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("TMDB_PredictionStore")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
SQLITE_PATH = os.path.join(DATA_DIR, "prediction_logs.db")

CACHE_TTL_SECONDS = 30

_PG_DDL = """
CREATE TABLE IF NOT EXISTS prediction_logs (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    release_year INT NOT NULL,
    runtime INT NOT NULL,
    budget BIGINT DEFAULT 0,
    original_language VARCHAR(10) NOT NULL,
    genres TEXT,
    predicted_probability FLOAT NOT NULL,
    is_popular BOOLEAN NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    model_architecture TEXT,
    poster_url TEXT
)
"""

_SQLITE_DDL = """
CREATE TABLE IF NOT EXISTS prediction_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    release_year INTEGER NOT NULL,
    runtime INTEGER NOT NULL,
    budget BIGINT DEFAULT 0,
    original_language TEXT NOT NULL,
    genres TEXT,
    predicted_probability REAL NOT NULL,
    is_popular BOOLEAN NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    model_architecture TEXT,
    poster_url TEXT
)
"""

_PG_MIGRATIONS = (
    "ALTER TABLE prediction_logs ADD COLUMN IF NOT EXISTS model_architecture TEXT",
    "ALTER TABLE prediction_logs ADD COLUMN IF NOT EXISTS poster_url TEXT",
)

_INSERT_COLUMNS = (
    "title, release_year, runtime, budget, original_language, "
    "genres, predicted_probability, is_popular, model_architecture, poster_url"
)


def _round(value: Optional[float], digits: int = 2) -> Optional[float]:
    return None if value is None else round(float(value), digits)


class PredictionStore:
    def __init__(self, database_url: Optional[str] = None, sqlite_path: str = SQLITE_PATH):
        self._database_url = database_url
        self._sqlite_path = sqlite_path
        self._lock = threading.Lock()
        self._backend: Optional[str] = None  # "postgresql" | "sqlite"
        self._version = 0  # bumped on every write -> invalidates the cache
        self._cache: Dict[Tuple[float, int], Tuple[int, float, Dict[str, Any]]] = {}

    # ------------------------------------------------------------------ #
    # Connection handling
    # ------------------------------------------------------------------ #
    @property
    def backend(self) -> Optional[str]:
        return self._backend

    def _database_url_value(self) -> Optional[str]:
        return self._database_url or os.getenv("DATABASE_URL")

    def _connect_pg(self):
        import psycopg2  # imported lazily: only needed when PostgreSQL is used

        return psycopg2.connect(self._database_url_value(), connect_timeout=3)

    def _connect_sqlite(self):
        os.makedirs(os.path.dirname(self._sqlite_path), exist_ok=True)
        return sqlite3.connect(self._sqlite_path)

    def _ensure_backend(self) -> str:
        if self._backend:
            return self._backend
        with self._lock:
            if self._backend:
                return self._backend
            if self._database_url_value():
                try:
                    conn = self._connect_pg()
                    try:
                        cur = conn.cursor()
                        cur.execute(_PG_DDL)
                        for statement in _PG_MIGRATIONS:
                            cur.execute(statement)
                        conn.commit()
                    finally:
                        conn.close()
                    self._backend = "postgresql"
                    logger.info("Prediction logs -> PostgreSQL")
                    return self._backend
                except Exception as e:
                    logger.warning(f"PostgreSQL unavailable ({e}); falling back to SQLite")
            conn = self._connect_sqlite()
            try:
                conn.execute(_SQLITE_DDL)
                columns = {row[1] for row in conn.execute("PRAGMA table_info(prediction_logs)")}
                for name in ("model_architecture", "poster_url"):
                    if name not in columns:
                        conn.execute(f"ALTER TABLE prediction_logs ADD COLUMN {name} TEXT")
                conn.commit()
            finally:
                conn.close()
            self._backend = "sqlite"
            logger.info(f"Prediction logs -> SQLite ({self._sqlite_path})")
            return self._backend

    def _connect(self):
        backend = self._ensure_backend()
        return self._connect_pg() if backend == "postgresql" else self._connect_sqlite()

    @property
    def _ph(self) -> str:
        """SQL placeholder style for the active driver."""
        return "%s" if self._backend == "postgresql" else "?"

    # ------------------------------------------------------------------ #
    # Writes
    # ------------------------------------------------------------------ #
    def log(self, entries: List[Dict[str, Any]]) -> bool:
        """Insert prediction rows. Never raises; returns False on failure."""
        if not entries:
            return True
        try:
            self._ensure_backend()
            ph = self._ph
            sql = (
                f"INSERT INTO prediction_logs ({_INSERT_COLUMNS}) "
                f"VALUES ({', '.join([ph] * 10)})"
            )
            rows = [
                (
                    str(e.get("title") or "Untitled Film")[:255],
                    int(e["release_year"]),
                    int(e["runtime"]),
                    int(e.get("budget") or 0),
                    str(e.get("original_language") or "en")[:10],
                    ", ".join(e.get("genres") or []),
                    float(e["probability"]),
                    bool(e["is_popular"]),
                    str(e.get("model_architecture") or "Multi-Layer Perceptron (MLP)"),
                    e.get("poster_url"),
                )
                for e in entries
            ]
            conn = self._connect()
            try:
                cur = conn.cursor()
                cur.executemany(sql, rows)
                conn.commit()
            finally:
                conn.close()
            self._version += 1
            return True
        except Exception as e:
            logger.warning(f"Could not log prediction(s): {e}")
            return False

    def history(self, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """Return recent prediction records in the shape used by the dashboard."""
        self._ensure_backend()
        ph = self._ph
        conn = self._connect()
        try:
            cur = conn.cursor()
            cur.execute(
                f"SELECT id, title, release_year, runtime, budget, original_language, genres, "
                f"predicted_probability, is_popular, created_at, model_architecture, poster_url "
                f"FROM prediction_logs ORDER BY id DESC LIMIT {ph} OFFSET {ph}",
                (limit, offset),
            )
            rows = cur.fetchall()
        finally:
            conn.close()

        return [
            {
                "id": row[0], "title": row[1], "release_year": row[2], "runtime": row[3],
                "budget": row[4], "original_language": row[5], "genres": row[6],
                "probability": float(row[7]), "predicted_probability": float(row[7]),
                "is_popular": bool(row[8]),
                "prediction": "Popular" if row[8] else "Kurang Populer",
                "created_at": row[9].isoformat() if hasattr(row[9], "isoformat") else row[9],
                "model_architecture": row[10] or "Multi-Layer Perceptron (MLP)",
                "poster_url": row[11],
            }
            for row in rows
        ]

    def delete(self, prediction_id: int) -> bool:
        """Delete one prediction log entry; return whether a row was removed."""
        self._ensure_backend()
        conn = self._connect()
        try:
            cur = conn.cursor()
            cur.execute(
                f"DELETE FROM prediction_logs WHERE id = {self._ph}",
                (prediction_id,),
            )
            deleted = cur.rowcount > 0
            conn.commit()
        finally:
            conn.close()
        if deleted:
            self._version += 1
        return deleted

    # ------------------------------------------------------------------ #
    # Analytics
    # ------------------------------------------------------------------ #
    def summary(self, min_probability: float = 0.5, top_genres: int = 5) -> Dict[str, Any]:
        """Aggregated insights over all logged predictions (cached, 30s TTL)."""
        key = (round(min_probability, 4), top_genres)
        cached = self._cache.get(key)
        now = time.time()
        if cached and cached[0] == self._version and now - cached[1] < CACHE_TTL_SECONDS:
            return {**cached[2], "cached": True}

        result = self._compute_summary(min_probability, top_genres)
        self._cache[key] = (self._version, now, result)
        return {**result, "cached": False}

    def _compute_summary(self, min_probability: float, top_genres: int) -> Dict[str, Any]:
        self._ensure_backend()
        ph = self._ph
        conn = self._connect()
        try:
            cur = conn.cursor()
            # One GROUP BY gives counts + averages per class; budget average only
            # counts reported budgets (> 0) because 0 means "unknown" in TMDB data.
            cur.execute(
                """
                SELECT is_popular,
                       COUNT(*),
                       AVG(runtime),
                       AVG(CASE WHEN budget > 0 THEN budget END),
                       SUM(CASE WHEN budget > 0 THEN 1 ELSE 0 END)
                FROM prediction_logs
                GROUP BY is_popular
                """
            )
            groups = cur.fetchall()
            cur.execute(
                f"SELECT genres FROM prediction_logs WHERE predicted_probability >= {ph}",
                (min_probability,),
            )
            genre_rows = cur.fetchall()
        finally:
            conn.close()

        stats = {True: None, False: None}
        for is_pop, count, avg_rt, avg_budget, budget_n in groups:
            stats[bool(is_pop)] = {
                "count": int(count),
                "avg_runtime": float(avg_rt) if avg_rt is not None else None,
                "avg_budget": float(avg_budget) if avg_budget is not None else None,
                "budget_reported": int(budget_n or 0),
            }

        def side(s: Optional[Dict[str, Any]]) -> Dict[str, Any]:
            if not s:
                return {"count": 0, "avg_runtime_minutes": None, "avg_budget_usd": None, "budget_reported_count": 0}
            return {
                "count": s["count"],
                "avg_runtime_minutes": _round(s["avg_runtime"], 1),
                "avg_budget_usd": _round(s["avg_budget"], 0),
                "budget_reported_count": s["budget_reported"],
            }

        pop, non = stats[True], stats[False]
        n_pop = pop["count"] if pop else 0
        n_non = non["count"] if non else 0
        total = n_pop + n_non

        # Overall averages = count-weighted mix of the two classes.
        rt_num = sum(s["avg_runtime"] * s["count"] for s in (pop, non) if s and s["avg_runtime"] is not None)
        bd_num = sum(s["avg_budget"] * s["budget_reported"] for s in (pop, non) if s and s["avg_budget"] is not None)
        bd_den = sum(s["budget_reported"] for s in (pop, non) if s)
        overall = {
            "count": total,
            "avg_runtime_minutes": _round(rt_num / total, 1) if total else None,
            "avg_budget_usd": _round(bd_num / bd_den, 0) if bd_den else None,
            "budget_reported_count": bd_den,
        }

        budget_ratio = None
        if pop and non and pop["avg_budget"] and non["avg_budget"]:
            budget_ratio = round(pop["avg_budget"] / non["avg_budget"], 2)
        runtime_diff = None
        if pop and non and pop["avg_runtime"] is not None and non["avg_runtime"] is not None:
            runtime_diff = round(pop["avg_runtime"] - non["avg_runtime"], 1)

        counter: Counter = Counter()
        for (genres,) in genre_rows:
            for g in (genres or "").split(","):
                g = g.strip()
                if g:
                    counter[g] += 1
        top = [
            {"genre": g, "count": c}
            for g, c in sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))[:top_genres]
        ]

        return {
            "total_predictions": total,
            "popularity_split": {
                "popular_count": n_pop,
                "kurang_populer_count": n_non,
                "popular_pct": round(100 * n_pop / total, 2) if total else 0.0,
                "kurang_populer_pct": round(100 * n_non / total, 2) if total else 0.0,
            },
            "top_scoring_genres": {
                "min_probability": min_probability,
                "predictions_considered": len(genre_rows),
                "genres": top,
            },
            "averages": {
                "overall": overall,
                "popular": side(pop),
                "kurang_populer": side(non),
                "budget_ratio_popular_vs_kurang_populer": budget_ratio,
                "runtime_diff_minutes_popular_minus_kurang_populer": runtime_diff,
            },
            "storage_backend": self._backend,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }


prediction_store = PredictionStore()
