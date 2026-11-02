import os
import sqlite3
import pandas as pd
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("TMDB_Indexer")

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
CSV_PATH = os.path.join(DATA_DIR, "TMDB_movie_dataset_v11.csv")
DB_PATH = os.path.join(DATA_DIR, "movies.db")

TMDB_BASE_POSTER_URL = "https://image.tmdb.org/t/p/w500"
TMDB_BASE_BACKDROP_URL = "https://image.tmdb.org/t/p/w1280"

# --- Blocklist: title/original_title patterns (exact substring match, case-insensitive) ---
TITLE_BLOCKLIST = [
    "jav", "av girl", "av idol", "j-cup", "k-cup", "f-cup", "g-cup", "h-cup",
    "big tits", "huge tits", "giant tits", "busty", "big boobs", "big breast",
    "nude beach", "naked girl", "sex tape", "sex video", "sex film", "sex movie",
    "porn star", "pornstar", "porno", "xxx",
    "hentai", "ecchi", "eroge",
    "massage parlor", "massage girl", "massage room", "massage shop", "massage sharing",
    "massage service", "tasty massage", "body massage",
    "excited ladies", "happy ending",
    "하룻밤", "흥분", "섹스", "에로", "야동", "야설",
    "j컵", "k컵", "巨乳", "爆乳", "美乳", "AV女優", "エロ動画", "無修正",
    "盗撮", "痴漢", "調教", "緊縛", "人妻", "不倫", "熟女",
    "girls sex", "women sex", "sex sharing", "sex massage",
    "lesbian sex", "teen sex", "family sex", "taboo sex",
    "business trip massage", "service for women",
    # Suspicious title word combos
    "is cheap in the", "mom 2", "mom 3", "mom 4", "stepmother sex",
    "stepmom sex", "sister sex", "brother sex",
]

# --- Blocklist: overview/description patterns ---
OVERVIEW_BLOCKLIST = [
    "jav", "softcore", "hardcore porn", "adult video", "erotic film",
    "j-cup", "k-cup", "huge breasts", "giant breasts", "massive tits", "big tits",
    "blowjob", "blow job", "hand job", "orgasm", "masturbat",
    "gangbang", "gang bang", "threesome", "cuckold", "voyeur", "bdsm", "fetish",
    "erotic massage", "massage parlor", "sex tape", "sex video",
    "nude idol", "nude model", "strip club", "pole dance",
    "prostitut", "escort service", "sex worker in", "call girl",
    "penis size", "vagina", "genitalia", "genital",
    "pinku eiga", "roman porno", "nikkatsu",
    "idol sex", "sexual fantasy", "sexual arousal", "sexual intercourse",
    "intimate scene", "intimate encounter", "bedroom scene",
    "share one sex", "enjoy sex", "not satisfied with", "after taking viagra",
    "business trip massage", "massage that he", "massage appointment",
    "special service for women", "satisfied! special",
    # Contextual Korean/Japanese adult indicators
    "흥분한 여자", "하룻밤의 정사", "여대생들", "주부의 외도",
    "J컵 미유", "에로 영화", "성인 영화", "야한 영화",
    "巨乳アイドル", "エロ映画", "成人映画", "セックス", "ヌード",
]

# --- Genre-based hard block ---
GENRE_BLOCKLIST = [
    "pornography", "adult", "erotic", "erotica",
]

SPECIAL_ASIAN_FILMS = [
    {
        "id": 16664,
        "title": "All About Lily Chou-Chou",
        "original_title": "リリイ・シュシュのすべて",
        "aliases": "lily chou-chou, lily chou chou, lily chouchou, lily chou, shunji iwai, riri shushu no subete, リリイ・シュシュのすべて",
        "release_year": 2001, "runtime": 146, "genres": "Drama, Crime, Music",
        "original_language": "ja", "budget": 2500000,
        "tagline": "Pain can take you in prison. The ether can set you free.",
        "overview": "Charts the troubled teenage years of students Yūichi Hasumi and Shūsuke Hoshino, exploring the shifting and complex power dynamics of their relationship against the backdrop of Yūichi's love for the dreamy and abstract music of fictional pop star Lily Chou-Chou.",
        "popularity": 22.3, "vote_count": 188, "vote_average": 7.7,
        "poster_path": "/qrN3oGKlMRrw5WbWYJ8ry9pnbxZ.jpg",
        "poster_url": f"{TMDB_BASE_POSTER_URL}/qrN3oGKlMRrw5WbWYJ8ry9pnbxZ.jpg",
        "backdrop_url": f"{TMDB_BASE_BACKDROP_URL}/k6BHXMBS7QACEuh2Nw1656OX4qT.jpg",
    },
    {
        "id": 1291559,
        "title": "Drawing Closer",
        "original_title": "余命一年の僕が、余命半年の君と出会った話。",
        "aliases": "drawing closer, yomei ichinen no boku",
        "release_year": 2024, "runtime": 118, "genres": "Romance, Drama",
        "original_language": "ja", "budget": 4000000,
        "tagline": "Two souls with limited time painting unforgettable memories.",
        "overview": "With only one year left to live, 17-year-old Akito finds new meaning in life when he meets a terminally ill girl with just six months left.",
        "popularity": 42.5, "vote_count": 120, "vote_average": 7.9,
        "poster_path": "/i2Tp1nD151qU4YAAm8NcZ91gUkQ.jpg",
        "poster_url": f"{TMDB_BASE_POSTER_URL}/i2Tp1nD151qU4YAAm8NcZ91gUkQ.jpg",
        "backdrop_url": f"{TMDB_BASE_BACKDROP_URL}/rLb2cwF3Pazuxaj0sRXQ037tGI1.jpg",
    },
    {
        "id": 508747,
        "title": "Us and Them",
        "original_title": "后来的我们",
        "aliases": "us and them, once we were us, hou lai de wo men, 后来的我们",
        "release_year": 2018, "runtime": 120, "genres": "Drama, Romance",
        "original_language": "zh", "budget": 10000000,
        "tagline": "Happiness is not about stories, but who is with you.",
        "overview": "Two strangers meet on a train and form a bond that evolves over the years through shared dreams, heartbreak, and reconciliations.",
        "popularity": 38.2, "vote_count": 210, "vote_average": 7.7,
        "poster_path": "/pzFusb9gwCBf1CbtIPqxs1DhfUG.jpg",
        "poster_url": f"{TMDB_BASE_POSTER_URL}/pzFusb9gwCBf1CbtIPqxs1DhfUG.jpg",
        "backdrop_url": f"{TMDB_BASE_BACKDROP_URL}/hiKmpZMGZsrkA3cdce8a7Dpos1j.jpg",
    },
    {
        "id": 36095,
        "title": "Cure",
        "original_title": "キュア",
        "aliases": "cure, kyua, kiyoshi kurosawa cure",
        "release_year": 1997, "runtime": 111, "genres": "Crime, Horror, Mystery, Thriller",
        "original_language": "ja", "budget": 1500000,
        "tagline": "Who are you?",
        "overview": "A wave of gruesome murders is being committed by disparate individuals who all carve an X into their victims' necks with no apparent motive, investigated by a troubled detective.",
        "popularity": 45.1, "vote_count": 680, "vote_average": 7.6,
        "poster_path": "/nLZ2AJFLtMoAAAD54mbT4exj1Wp.jpg",
        "poster_url": f"{TMDB_BASE_POSTER_URL}/nLZ2AJFLtMoAAAD54mbT4exj1Wp.jpg",
        "backdrop_url": f"{TMDB_BASE_BACKDROP_URL}/whQNdxw6K8PsqYv3q1Z7cQoJ712.jpg",
    },
    {
        "id": 1409771,
        "title": "Once We Were Us",
        "original_title": "Once We Were Us",
        "aliases": "once we were us, when we were us",
        "release_year": 2024, "runtime": 105, "genres": "Romance, Drama",
        "original_language": "zh", "budget": 3000000,
        "tagline": "Remembering the seasons when love was simple.",
        "overview": "A nostalgic exploration of youth, dreams, and the unrepeatable intimacy of early love.",
        "popularity": 28.4, "vote_count": 45, "vote_average": 7.4,
        "poster_path": "/5THeOOLV8O7F4temLtgCuvOQNWv.jpg",
        "poster_url": f"{TMDB_BASE_POSTER_URL}/5THeOOLV8O7F4temLtgCuvOQNWv.jpg",
        "backdrop_url": f"{TMDB_BASE_BACKDROP_URL}/yF1eOkaYvwiORauRCPWznV9xVvi.jpg",
    },
]

def is_adult_content(title: str, original_title: str, overview: str, genres: str) -> bool:
    """Multi-signal adult content check across title, overview, and genres."""
    t_low = (title or "").lower()
    ot_low = (original_title or "").lower()
    ov_low = (overview or "").lower()
    g_low = (genres or "").lower()

    for block in TITLE_BLOCKLIST:
        if block in t_low or block in ot_low:
            return True

    for block in OVERVIEW_BLOCKLIST:
        if block in ov_low:
            return True

    for block in GENRE_BLOCKLIST:
        if block in g_low:
            return True

    return False

def build_database():
    if not os.path.exists(CSV_PATH):
        logger.error(f"CSV not found at {CSV_PATH}")
        return

    logger.info(f"Building filtered SQLite database at {DB_PATH}...")
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE movies (
            id INTEGER PRIMARY KEY,
            title TEXT, original_title TEXT,
            title_lower TEXT, original_title_lower TEXT, aliases TEXT,
            genres TEXT, release_year INTEGER, runtime INTEGER,
            original_language TEXT, budget REAL, tagline TEXT, overview TEXT,
            popularity REAL, vote_count INTEGER, vote_average REAL,
            poster_path TEXT, poster_url TEXT, backdrop_url TEXT
        )
    """)
    cursor.execute("CREATE INDEX idx_title_lower ON movies(title_lower);")
    cursor.execute("CREATE INDEX idx_orig_title_lower ON movies(original_title_lower);")
    cursor.execute("CREATE INDEX idx_aliases ON movies(aliases);")
    cursor.execute("CREATE INDEX idx_pop ON movies(popularity DESC);")
    cursor.execute("CREATE INDEX idx_vote ON movies(vote_count DESC);")

    chunksize = 100_000
    total_inserted = 0
    total_blocked = 0

    use_cols = [
        "id", "title", "original_title", "genres", "release_date",
        "runtime", "original_language", "budget", "tagline", "overview",
        "popularity", "vote_count", "vote_average",
        "poster_path", "backdrop_path", "adult"
    ]

    for chunk_idx, chunk in enumerate(pd.read_csv(CSV_PATH, chunksize=chunksize, usecols=use_cols, low_memory=False)):
        # Hard adult flag
        chunk = chunk[chunk["adult"].astype(str).str.lower() != "true"]
        chunk = chunk[chunk["title"].notnull()]

        rows = []
        for _, r in chunk.iterrows():
            t = str(r["title"]).strip()
            ot = str(r["original_title"]).strip() if pd.notnull(r["original_title"]) else ""
            ov = str(r["overview"]) if pd.notnull(r["overview"]) else ""
            gn = str(r["genres"]) if pd.notnull(r["genres"]) else ""

            # Multi-signal adult filter
            if is_adult_content(t, ot, ov, gn):
                total_blocked += 1
                continue

            # Quality gate: needs poster OR popularity > 0.8 OR vote_count >= 5
            p_path = str(r["poster_path"]) if pd.notnull(r["poster_path"]) and str(r["poster_path"]).startswith("/") else None
            pop = float(r["popularity"]) if pd.notnull(r["popularity"]) else 0.0
            vc = int(float(r["vote_count"])) if pd.notnull(r["vote_count"]) else 0

            has_poster = p_path is not None
            if not (has_poster and pop >= 0.3) and pop < 0.8 and vc < 5:
                continue

            mid = int(float(r["id"])) if pd.notnull(r["id"]) else 0
            p_url = f"{TMDB_BASE_POSTER_URL}{p_path}" if p_path else None

            b_path = str(r["backdrop_path"]) if pd.notnull(r["backdrop_path"]) and str(r["backdrop_path"]).startswith("/") else None
            b_url = f"{TMDB_BASE_BACKDROP_URL}{b_path}" if b_path else None

            rel_date = str(r.get("release_date", ""))
            year = int(rel_date[:4]) if len(rel_date) >= 4 and rel_date[:4].isdigit() else None
            runtime = int(float(r["runtime"])) if pd.notnull(r["runtime"]) and float(r["runtime"]) > 0 else 0
            budget = float(r["budget"]) if pd.notnull(r["budget"]) and float(r["budget"]) > 0 else 0.0
            va = float(r["vote_average"]) if pd.notnull(r["vote_average"]) else 0.0

            rows.append((
                mid, t, ot, t.lower(), ot.lower(), "",
                gn, year, runtime,
                str(r["original_language"]) if pd.notnull(r["original_language"]) else "en",
                budget,
                str(r["tagline"]) if pd.notnull(r["tagline"]) else "",
                ov, pop, vc, va, p_path, p_url, b_url
            ))

        cursor.executemany("""
            INSERT OR REPLACE INTO movies (
                id, title, original_title, title_lower, original_title_lower, aliases,
                genres, release_year, runtime, original_language, budget, tagline,
                overview, popularity, vote_count, vote_average, poster_path, poster_url, backdrop_url
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, rows)
        conn.commit()
        total_inserted += len(rows)
        logger.info(f"Chunk {chunk_idx + 1}: inserted {len(rows):,}, blocked {total_blocked:,} total")

    # Insert curated Special Asian Films (override/upsert)
    for sf in SPECIAL_ASIAN_FILMS:
        cursor.execute("""
            INSERT OR REPLACE INTO movies (
                id, title, original_title, title_lower, original_title_lower, aliases,
                genres, release_year, runtime, original_language, budget, tagline,
                overview, popularity, vote_count, vote_average, poster_path, poster_url, backdrop_url
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            sf["id"], sf["title"], sf["original_title"], sf["title"].lower(), sf["original_title"].lower(),
            sf["aliases"], sf["genres"], sf["release_year"], sf["runtime"], sf["original_language"],
            sf["budget"], sf["tagline"], sf["overview"], sf["popularity"], sf["vote_count"],
            sf["vote_average"], sf["poster_path"], sf["poster_url"], sf["backdrop_url"]
        ))
    conn.commit()
    conn.close()
    logger.info(f"Done. Indexed: {total_inserted + len(SPECIAL_ASIAN_FILMS):,} | Blocked adult: {total_blocked:,}")

if __name__ == "__main__":
    build_database()
