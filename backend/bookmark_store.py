"""Persistent movie bookmarks, using PostgreSQL in Compose and SQLite locally."""
import os
import sqlite3
from typing import Any, Dict, List, Optional

import psycopg2

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SQLITE_PATH = os.path.join(BASE_DIR, "data", "bookmarked_movies.db")

_PG_DDL = """
CREATE TABLE IF NOT EXISTS bookmarked_movies (
    id SERIAL PRIMARY KEY,
    movie_id BIGINT NOT NULL UNIQUE,
    title VARCHAR(255) NOT NULL,
    poster_path TEXT,
    release_date VARCHAR(50),
    vote_average DOUBLE PRECISION,
    added_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
)
"""
_SQLITE_DDL = """
CREATE TABLE IF NOT EXISTS bookmarked_movies (
    movie_id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    poster_path TEXT,
    release_date TEXT,
    vote_average REAL,
    added_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
)
"""


class BookmarkStore:
    def __init__(self, database_url: Optional[str] = None, sqlite_path: str = SQLITE_PATH):
        self.database_url = database_url
        self.sqlite_path = sqlite_path

    def _url(self) -> Optional[str]:
        return self.database_url or os.getenv("DATABASE_URL")

    def _connect(self):
        url = self._url()
        if url:
            return psycopg2.connect(url, connect_timeout=int(os.getenv("DB_CONNECT_TIMEOUT", "3")))
        os.makedirs(os.path.dirname(self.sqlite_path), exist_ok=True)
        return sqlite3.connect(self.sqlite_path)

    def _ensure_table(self, conn) -> None:
        cur = conn.cursor()
        cur.execute(_PG_DDL if self._url() else _SQLITE_DDL)
        if self._url():
            # Upgrade installations created with the earlier, non-unique schema.
            cur.execute("ALTER TABLE bookmarked_movies ADD COLUMN IF NOT EXISTS movie_id BIGINT")
            cur.execute("ALTER TABLE bookmarked_movies ADD COLUMN IF NOT EXISTS poster_path TEXT")
            cur.execute("ALTER TABLE bookmarked_movies ADD COLUMN IF NOT EXISTS release_date VARCHAR(50)")
            cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS bookmarked_movies_movie_id_uq ON bookmarked_movies (movie_id)")
        conn.commit()

    def list(self) -> List[Dict[str, Any]]:
        conn = self._connect()
        try:
            self._ensure_table(conn)
            cur = conn.cursor()
            cur.execute("SELECT movie_id, title, poster_path, release_date, vote_average, added_at FROM bookmarked_movies WHERE movie_id IS NOT NULL ORDER BY added_at DESC")
            rows = cur.fetchall()
            cols = ["movie_id", "title", "poster_path", "release_date", "vote_average", "added_at"]
            return [dict(zip(cols, row)) for row in rows]
        finally:
            conn.close()

    def add(self, movie: Dict[str, Any]) -> bool:
        conn = self._connect()
        try:
            self._ensure_table(conn)
            cur = conn.cursor()
            if self._url():
                cur.execute("INSERT INTO bookmarked_movies (movie_id, title, poster_path, release_date, vote_average) VALUES (%s, %s, %s, %s, %s) ON CONFLICT (movie_id) DO NOTHING RETURNING movie_id", tuple(movie[k] for k in ("movie_id", "title", "poster_path", "release_date", "vote_average")))
            else:
                cur.execute("INSERT OR IGNORE INTO bookmarked_movies (movie_id, title, poster_path, release_date, vote_average) VALUES (?, ?, ?, ?, ?)", tuple(movie[k] for k in ("movie_id", "title", "poster_path", "release_date", "vote_average")))
            inserted = cur.fetchone() is not None if self._url() else cur.rowcount > 0
            conn.commit()
            return inserted
        finally:
            conn.close()

    def delete(self, movie_id: int) -> bool:
        conn = self._connect()
        try:
            self._ensure_table(conn)
            cur = conn.cursor()
            cur.execute("DELETE FROM bookmarked_movies WHERE movie_id = %s" if self._url() else "DELETE FROM bookmarked_movies WHERE movie_id = ?", (movie_id,))
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()


bookmark_store = BookmarkStore()
