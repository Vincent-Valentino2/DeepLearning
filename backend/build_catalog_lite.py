"""Builds the compact movie catalog shipped with the backend for hosts without data/movies.db.

The full index (data/movies.db, ~525 MB, built by backend/build_index.py) is too large for the
repository or a Vercel function. This keeps the recognisable films (poster + at least
MIN_VOTES votes) with the same schema, so search_movies_from_db() works unchanged, and
gzips the result to backend/catalog/movies_lite.db.gz (~8 MB).

    backend/.venv/bin/python -m backend.build_catalog_lite
"""
import gzip
import os
import shutil
import sqlite3
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE = os.path.join(ROOT, "data", "movies.db")
TARGET = os.path.join(ROOT, "backend", "catalog", "movies_lite.db.gz")
MIN_VOTES = 50


def build() -> None:
    if not os.path.exists(SOURCE):
        raise SystemExit(f"{SOURCE} not found; run `python -m backend.build_index` first")
    with tempfile.TemporaryDirectory() as tmp:
        lite = os.path.join(tmp, "movies_lite.db")
        conn = sqlite3.connect(lite)
        conn.execute("ATTACH DATABASE ? AS src", (SOURCE,))
        conn.execute("CREATE TABLE movies AS SELECT * FROM src.movies "
                     "WHERE poster_url IS NOT NULL AND vote_count >= ? ORDER BY id", (MIN_VOTES,))
        conn.commit()
        conn.execute("DETACH DATABASE src")
        for column in ("title_lower", "original_title_lower", "aliases"):
            conn.execute(f"CREATE INDEX idx_{column} ON movies({column})")
        conn.execute("CREATE INDEX idx_pop ON movies(popularity DESC)")
        count = conn.execute("SELECT COUNT(*) FROM movies").fetchone()[0]
        conn.commit()
        conn.execute("VACUUM")
        conn.close()
        os.makedirs(os.path.dirname(TARGET), exist_ok=True)
        # mtime=0 keeps the gzip byte-identical across rebuilds of the same data
        with open(lite, "rb") as src, open(TARGET, "wb") as raw, \
                gzip.GzipFile(filename="movies_lite.db", mode="wb", fileobj=raw, mtime=0, compresslevel=9) as dst:
            shutil.copyfileobj(src, dst)
    print(f"{count:,} films -> {TARGET} ({os.path.getsize(TARGET) / 1e6:.1f} MB)")


if __name__ == "__main__":
    build()
