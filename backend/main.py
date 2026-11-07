import os
import glob
import json
import sqlite3
import logging
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, HTTPException, Path, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import numpy as np
import pandas as pd
import joblib

from backend.data_processor import (
    extract_cinephile_features,
    STANDARD_GENRES,
    TOP_LANGUAGES,
)
from backend.prediction_store import prediction_store
from backend.bookmark_store import bookmark_store

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TMDB_API")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "movies.db")
MODELS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
MODEL_PATH = os.path.join(MODELS_DIR, "mlp_model.joblib")

TMDB_BASE_POSTER_URL = "https://image.tmdb.org/t/p/w500"
TMDB_BASE_BACKDROP_URL = "https://image.tmdb.org/t/p/w1280"

app = FastAPI(
    title="TMDB Movie Popularity MLP API",
    description="Backend API for predicting TMDB movie popularity classification (Popular vs Kurang Populer) based on metadata.",
    version="1.2.0",
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

TMDB_GENRES = [
    "Action", "Adventure", "Animation", "Comedy", "Crime",
    "Documentary", "Drama", "Family", "Fantasy", "History",
    "Horror", "Music", "Mystery", "Romance", "Science Fiction",
    "TV Movie", "Thriller", "War", "Western",
]

COMMON_LANGUAGES = [
    {"code": "en", "name": "English"},
    {"code": "ja", "name": "Japanese (日本語)"},
    {"code": "ko", "name": "Korean (한국어)"},
    {"code": "fr", "name": "French (Français)"},
    {"code": "es", "name": "Spanish (Español)"},
    {"code": "id", "name": "Indonesian (Bahasa Indonesia)"},
    {"code": "de", "name": "German (Deutsch)"},
    {"code": "it", "name": "Italian (Italiano)"},
    {"code": "zh", "name": "Chinese (中文)"},
    {"code": "hi", "name": "Hindi (हिन्दी)"},
    {"code": "pt", "name": "Portuguese (Português)"},
    {"code": "ru", "name": "Russian (Русский)"},
]

TOP_LANGUAGES = ["en", "ja", "ko", "fr", "es", "id", "de", "it", "zh", "hi", "ru", "pt", "other"]

# Global Model Artifact Cache
model_cache: Dict[str, Any] = {}
_last_model_mtime: float = 0.0

def load_trained_model(force: bool = False):
    global model_cache, _last_model_mtime
    if os.path.exists(MODEL_PATH):
        try:
            mtime = os.path.getmtime(MODEL_PATH)
            if force or mtime > _last_model_mtime or "model" not in model_cache:
                artifact = joblib.load(MODEL_PATH)
                model_cache = artifact
                _last_model_mtime = mtime
                logger.info(f"Loaded trained MLP model v2.0 from {MODEL_PATH} (features: {artifact.get('feature_count', 'auto')})")
        except Exception as e:
            logger.error(f"Failed to load model from {MODEL_PATH}: {e}")
            if force:
                model_cache = {}
    else:
        logger.warning(f"No trained model found at {MODEL_PATH}")
        model_cache = {}

load_trained_model()

def search_movies_from_db(q: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Clean, safe, highly relevant movie search using indexed SQLite database."""
    if not os.path.exists(DB_PATH):
        return []

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    q_clean = q.strip().lower()

    if not q_clean:
        # Return prominent high-popularity films
        c.execute("""
            SELECT * FROM movies
            WHERE poster_url IS NOT NULL AND popularity >= 20
            ORDER BY popularity DESC, vote_count DESC
            LIMIT ?
        """, (limit,))
    elif len(q_clean) <= 2:
        # Single or 2-letter search (e.g. "l"): prioritize most popular recognizable films starting with L or "The L"
        c.execute("""
            SELECT * FROM movies
            WHERE (title_lower LIKE ? OR title_lower LIKE ? OR original_title_lower LIKE ?)
              AND poster_url IS NOT NULL
              AND vote_count >= 5
            ORDER BY 
                CASE 
                    WHEN title_lower = ? THEN 1
                    WHEN title_lower LIKE ? THEN 2
                    ELSE 3
                END,
                popularity DESC, 
                vote_count DESC
            LIMIT ?
        """, (f"{q_clean}%", f"the {q_clean}%", f"{q_clean}%", q_clean, f"{q_clean}%", limit))
    else:
        # Multi-character search with relevance scoring
        c.execute("""
            SELECT * FROM movies
            WHERE (title_lower LIKE ? OR original_title_lower LIKE ? OR aliases LIKE ?)
              AND poster_url IS NOT NULL
            ORDER BY 
                CASE 
                    WHEN title_lower = ? THEN 1
                    WHEN original_title_lower = ? THEN 2
                    WHEN aliases LIKE ? THEN 3
                    WHEN title_lower LIKE ? THEN 4
                    WHEN title_lower LIKE ? THEN 5
                    ELSE 6 
                END,
                popularity DESC, 
                vote_count DESC
            LIMIT ?
        """, (
            f"%{q_clean}%", f"%{q_clean}%", f"%{q_clean}%",
            q_clean, q_clean, f"%{q_clean}%", f"{q_clean}%", f"% {q_clean}%", limit
        ))

    rows = c.fetchall()
    results = []
    for r in rows:
        genres_raw = r["genres"] or ""
        genres_list = [g.strip() for g in genres_raw.split(",") if g.strip()] if isinstance(genres_raw, str) else []
        results.append({
            "id": r["id"],
            "title": r["title"],
            "original_title": r["original_title"],
            "release_year": r["release_year"],
            "runtime": r["runtime"],
            "genres": genres_list,
            "original_language": r["original_language"],
            "budget": r["budget"],
            "tagline": r["tagline"],
            "overview": r["overview"],
            "poster_path": r["poster_path"],
            "poster_url": r["poster_url"],
            "backdrop_url": r["backdrop_url"],
            "popularity": r["popularity"],
            "vote_count": r["vote_count"],
            "vote_average": r["vote_average"],
        })
    conn.close()
    return results

class MoviePredictionRequest(BaseModel):
    title: Optional[str] = Field(default="Untitled Film", description="Film title for display")
    genres: List[str] = Field(default=["Drama"], description="List of genres")
    release_year: int = Field(default=2024, ge=1880, le=2035, description="Year of release")
    runtime: int = Field(default=110, ge=1, le=600, description="Runtime in minutes")
    original_language: str = Field(default="en", description="Original language code")
    budget: float = Field(default=15_000_000.0, ge=0.0, description="Budget in USD")
    poster_path: Optional[str] = Field(default=None, description="TMDB relative poster path")
    poster_url: Optional[str] = Field(default=None, description="Direct URL to poster image")
    tagline: Optional[str] = Field(default=None, description="Film tagline")
    overview: Optional[str] = Field(default=None, description="Film overview")

class MoviePredictionResponse(BaseModel):
    title: str
    prediction: str  # "Popular" or "Kurang Populer"
    is_popular: bool
    probability: float  # 0.0 to 1.0
    threshold_percentile: str  # "Top 25% (75th Percentile TMDB Popularity Threshold)"
    confidence_level: str  # "High", "Moderate", "Standard"
    model_architecture: str  # "Multi-Layer Perceptron (MLP)"
    input_features: dict
    feature_insights: List[str]
    poster_url: Optional[str] = None
    tagline: Optional[str] = None
    overview: Optional[str] = None

@app.get("/")
def root():
    return {
        "service": "TMDB Movie Popularity MLP API",
        "status": "online",
        "version": "1.2.0"
    }

def _git_commit_sha() -> str:
    """Commit SHA baked in at build time, falling back to the local checkout."""
    sha = os.getenv("GIT_COMMIT_SHA", "").strip()
    if sha:
        return sha
    try:
        import subprocess
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=BASE_DIR,
            capture_output=True, text=True, timeout=2, check=True,
        ).stdout.strip() or "unknown"
    except Exception:
        return "unknown"


RELEASE_INFO = {
    "commit_sha": _git_commit_sha(),
    "environment": os.getenv("RELEASE_ENV", "development"),
    "version": app.version,
}


@app.get("/api/health")
def health_check():
    has_model = "model" in model_cache
    database = prediction_store.ping()
    return {
        # The API itself is up; a database outage is reported as "degraded"
        # with HTTP 200 so container healthchecks don't restart the backend.
        "status": "healthy" if database["connected"] else "degraded",
        "database": database,
        "release": RELEASE_INFO,
        "model_loaded": has_model,
        "framework": "FastAPI + scikit-learn MLP (Multi-Layer Perceptron)",
        "port": 8001,
        "features_used": ["genres", "release_year", "runtime", "original_language", "budget"],
        "excluded_features": ["popularity", "vote_count", "vote_average"],
        "target": "Binary Classification (Top 25% Popular vs Kurang Populer)",
        "popularity_threshold": model_cache.get("popularity_threshold", 3.389) if has_model else "Dynamic 75th percentile"
    }

@app.get("/api/data/status")
def dataset_status():
    csv_candidates = glob.glob(os.path.join(DATA_DIR, "*.csv"))
    csv_candidates.sort(key=lambda f: os.path.getsize(f), reverse=True)
    has_csv = len(csv_candidates) > 0
    primary_csv = csv_candidates[0] if has_csv else None
    csv_size_mb = round(os.path.getsize(primary_csv) / (1024 * 1024), 2) if primary_csv else 0

    db_exists = os.path.exists(DB_PATH)
    total_indexed = 0
    if db_exists:
        try:
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM movies")
            total_indexed = cur.fetchone()[0]
            conn.close()
        except:
            total_indexed = 0

    has_model = "model" in model_cache
    metrics = model_cache.get("metrics", {}) if has_model else {}

    return {
        "dataset_directory": DATA_DIR,
        "has_csv_dataset": has_csv,
        "csv_filename": os.path.basename(primary_csv) if primary_csv else "TMDB_movie_dataset_v11.csv",
        "csv_size_mb": csv_size_mb,
        "database_indexed": db_exists,
        "catalog_entries_count": total_indexed,
        "model_trained": has_model,
        "model_metrics": metrics,
        "popularity_threshold_75th": model_cache.get("popularity_threshold", 3.389)
    }

@app.get("/api/movies/search")
def search_movies(q: str = Query("", description="Movie title search query"), limit: int = 10):
    results = search_movies_from_db(q, limit=limit)
    return {
        "query": q,
        "count": len(results),
        "results": results
    }

@app.get("/api/metadata/options")
def get_metadata_options():
    return {
        "genres": TMDB_GENRES,
        "languages": COMMON_LANGUAGES,
        "runtime_presets": [
            {"label": "Short (< 90m)", "value": 85},
            {"label": "Standard Feature (90-120m)", "value": 110},
            {"label": "Epic / Long (> 120m)", "value": 155},
        ],
        "budget_presets": [
            {"label": "Micro / Indie ($1M)", "value": 1_000_000},
            {"label": "Mid-tier ($25M)", "value": 25_000_000},
            {"label": "Blockbuster ($150M+)", "value": 150_000_000},
        ]
    }

# ==========================================
# BOOKMARKS & WATCHLIST API
# ==========================================
BOOKMARKS_DB_PATH = os.path.join(DATA_DIR, "bookmarks.db")


def init_bookmarks_table():
    try:
        conn = sqlite3.connect(BOOKMARKS_DB_PATH)
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS bookmarked_movies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL UNIQUE,
                release_year INTEGER,
                runtime INTEGER,
                genres TEXT,
                poster_url TEXT,
                vote_average REAL,
                original_language TEXT,
                tagline TEXT,
                overview TEXT,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Add fields to existing databases created before bookmark details were stored.
        c.execute("PRAGMA table_info(bookmarked_movies)")
        columns = {row[1] for row in c.fetchall()}
        for column in ("tagline", "overview"):
            if column not in columns:
                c.execute(f"ALTER TABLE bookmarked_movies ADD COLUMN {column} TEXT")
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning(f"Failed to init bookmarks table: {e}")

init_bookmarks_table()

class BookmarkPayload(BaseModel):
    movie_id: int = Field(gt=0)
    title: str
    poster_path: Optional[str] = None
    release_date: Optional[str] = None
    vote_average: Optional[float] = None

@app.get("/api/bookmarks")
def get_bookmarks():
    try:
        results = bookmark_store.list()
        return {"bookmarks": results, "total": len(results)}
    except Exception as e:
        logger.error(f"Error fetching bookmarks: {e}")
        raise HTTPException(status_code=500, detail="Bookmarks are unavailable")

@app.post("/api/bookmarks")
def add_bookmark(item: BookmarkPayload):
    try:
        inserted = bookmark_store.add(item.model_dump())
        if not inserted:
            raise HTTPException(status_code=409, detail={
                "status": "duplicate",
                "message": f"'{item.title}' is already bookmarked",
            })
        return {"status": "success", "message": f"'{item.title}' bookmarked successfully"}
    except Exception as e:
        logger.error(f"Error adding bookmark: {e}")
        raise HTTPException(status_code=500, detail="Could not save bookmark")

@app.delete("/api/bookmarks/{movie_id}")
def delete_bookmark(movie_id: int):
    try:
        removed = bookmark_store.delete(movie_id)
        if not removed:
            raise HTTPException(status_code=404, detail="Bookmark not found")
        return {"status": "success", "message": "Bookmark removed"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting bookmark: {e}")
        raise HTTPException(status_code=500, detail="Could not remove bookmark")


@app.get("/api/predictions")
@app.get("/api/predictions/history")
def get_prediction_history(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """Return recent genuine inference events for the dashboard history and audit table."""
    try:
        rows = prediction_store.history(limit=limit, offset=offset)
        return {"predictions": rows, "total": len(rows)}
    except Exception as e:
        logger.error(f"Error fetching prediction history: {e}")
        raise HTTPException(status_code=500, detail="Prediction history is unavailable")


@app.delete("/api/predictions/history/{prediction_id}")
def delete_prediction_history(prediction_id: int = Path(..., ge=1)):
    """Delete one prediction log entry by its database ID."""
    try:
        deleted = prediction_store.delete(prediction_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Prediction history entry not found")
        return {"status": "success", "deleted_id": prediction_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting prediction history entry {prediction_id}: {e}")
        raise HTTPException(status_code=500, detail="Prediction history entry could not be deleted")



# ==========================================
# INFERENCE HELPERS (shared by /api/predict and /api/compare)
# ==========================================
def _mlp_probabilities(payloads: List[MoviePredictionRequest]) -> List[Optional[float]]:
    """One batched MLP forward pass. Returns None for every row if the model is unavailable."""
    load_trained_model()
    if "model" not in model_cache:
        return [None] * len(payloads)
    try:
        mlp = model_cache["model"]
        df_input = pd.DataFrame([{
            "title": p.title,
            "release_year": p.release_year,
            "runtime": p.runtime,
            "genres": ", ".join(p.genres),
            "original_language": p.original_language,
            "budget": p.budget,
        } for p in payloads])

        X_input, _ = extract_cinephile_features(
            df_input,
            scaler_budget=model_cache.get("scaler_budget"),
            scaler_runtime=model_cache.get("scaler_runtime"),
            fit_scalers=False
        )
        return [float(p) for p in mlp.predict_proba(X_input)[:, 1]]
    except Exception as e:
        logger.warning(f"Error during MLP inference, falling back: {e}")
        return [None] * len(payloads)


def _build_prediction(payload: MoviePredictionRequest, prob: Optional[float]) -> MoviePredictionResponse:
    """Turns an MLP probability (or None -> heuristic fallback) into the full API response."""
    poster_url = payload.poster_url
    if not poster_url and payload.poster_path:
        if payload.poster_path.startswith("/"):
            poster_url = f"{TMDB_BASE_POSTER_URL}{payload.poster_path}"
        else:
            poster_url = payload.poster_path

    model_name = "Multi-Layer Perceptron (MLP) v2.0 - Cinephile Weights"

    insights = []
    input_genres = set(payload.genres)
    lang = payload.original_language.lower()
    year = payload.release_year
    runtime = payload.runtime
    budget = payload.budget

    # 1. Articulate Specific Genre Affinity Synergies
    has_drama = "Drama" in input_genres
    has_war = "War" in input_genres
    has_scifi = "Science Fiction" in input_genres
    has_romance = "Romance" in input_genres
    has_comedy = "Comedy" in input_genres
    has_crime = "Crime" in input_genres
    has_thriller = "Thriller" in input_genres
    has_mystery = "Mystery" in input_genres
    has_action = "Action" in input_genres
    has_adventure = "Adventure" in input_genres
    has_animation = "Animation" in input_genres
    has_fantasy = "Fantasy" in input_genres

    if has_war and has_drama:
        insights.append("Genre Affinity: [War + Drama] represents a monumental historical prestige synergy with profound critical reverence (e.g. Come and See, Apocalypse Now).")
    elif has_scifi and has_drama:
        insights.append("Genre Affinity: [Science Fiction + Drama] represents a high-affinity philosophical sci-fi synergy with dedicated cult followings (e.g. Stalker, Solaris, Interstellar).")
    elif has_romance and (has_comedy or has_drama):
        insights.append("Genre Affinity: [Romance + Drama/Comedy] carries high emotional affinity and auteur cinephile resonance (e.g. Chungking Express, Us and Them).")
    elif has_crime and (has_mystery or has_thriller or has_drama):
        insights.append("Genre Affinity: [Crime + Mystery/Thriller] drives strong psychological tension and cult noir engagement (e.g. Cure, All About Lily Chou-Chou).")
    elif has_animation and (has_fantasy or has_adventure):
        insights.append("Genre Affinity: [Animation + Fantasy/Adventure] holds boundless multi-generational global appeal (e.g. Spirited Away, Your Name).")
    elif has_action and has_adventure:
        insights.append("Genre Affinity: [Action + Adventure] commands broad blockbuster theatrical attraction (e.g. Dune).")
    elif len(input_genres) > 0:
        insights.append(f"Genre Portfolio: Combines {', '.join(payload.genres)} for targeted thematic reach.")

    # 2. Articulate Cultural Tradition & Fair Country Evaluation (De-biasing)
    if lang in ["ru", "pl", "uk", "cs"]:
        insights.append("Cultural Sphere: Slavic & Eastern European cinematic tradition evaluated fairly without Anglophone or TMDB scrape bias.")
    elif lang in ["cn", "zh", "yue"]:
        insights.append("Cultural Sphere: Hong Kong & Chinese auteur cinema (e.g. Wong Kar-wai tradition) carries immense global cinephile prestige.")
    elif lang in ["fr", "it", "de", "es", "sv"]:
        insights.append("Cultural Sphere: Continental European cinema celebrated for auteur festival impact and dedicated critical circles.")
    elif lang == "ja":
        insights.append("Cultural Sphere: Japanese cinema evaluated on artistic merit, balancing indie auteur prestige with modern catalog interest.")
    elif lang == "en":
        insights.append("Cultural Sphere: Global Anglophone distribution network provides expansive baseline reach.")
    else:
        insights.append(f"Cultural Sphere: International catalog representation ({lang.upper()}) evaluated neutrally.")

    # 3. Articulate Era Dynamics & Cult Longevity
    if year < 1985:
        insights.append(f"Era Dynamics: Vintage golden age ({year}) — recognized for enduring canonical durability and lifelong cinephile devotion.")
    elif 1985 <= year < 2005:
        insights.append(f"Era Dynamics: Retro cult renaissance ({year}) — sustained modern streaming vitality and active revival screenings.")
    elif year >= 2020:
        insights.append(f"Era Dynamics: Contemporary modern release ({year}) — immediate platform discourse and digital discovery.")

    # 4. Articulate Pacing & Scale
    if runtime >= 135:
        insights.append(f"Epic Pacing: Expansive runtime ({runtime}m) accommodates profound narrative depth and deliberate auteur pacing.")
    elif 88 <= runtime <= 130:
        insights.append(f"Exhibition Pacing: Feature duration ({runtime}m) matches standard theatrical and cinephile viewing sweet spots.")

    # 5. Articulate Budget Profile
    if budget >= 50_000_000:
        insights.append(f"Production Scale: Major studio investment (${budget:,.0f}) provides wide marketing penetration.")
    elif budget < 3_000_000 and (prob is not None and prob >= 0.50):
        insights.append("Prestige Scale: Modest/unreported USD budget successfully counterbalanced by exceptional genre affinity and cinematic duration.")

    if prob is None:
        # Balanced heuristic fallback
        base_score = 0.45
        if has_war and has_drama: base_score += 0.25
        if has_scifi and has_drama: base_score += 0.25
        if has_romance and (has_comedy or has_drama): base_score += 0.20
        if has_crime and (has_mystery or has_thriller or has_drama): base_score += 0.22
        if has_action and has_adventure: base_score += 0.25
        if has_animation and has_fantasy: base_score += 0.25

        if lang in ["ru", "cn", "zh", "ja", "fr", "it", "de", "en", "ko"]:
            base_score += 0.10

        if year < 2000 and runtime >= 95 and (has_drama or has_scifi or has_war or has_crime or has_romance):
            base_score += 0.15 # Vintage cult resilience!

        if budget >= 40_000_000:
            base_score += 0.20

        prob = max(0.05, min(0.99, base_score))
        model_name = "Multi-Layer Perceptron (MLP) v2.0 - Cinephile Heuristic"

    is_popular = bool(prob >= 0.50)
    diff = abs(prob - 0.50)
    confidence = "High" if diff >= 0.25 else ("Moderate" if diff >= 0.10 else "Low (Borderline)")

    response = MoviePredictionResponse(
        title=payload.title or "Untitled Film",
        prediction="Popular" if is_popular else "Kurang Populer",
        is_popular=is_popular,
        probability=round(prob, 4),
        threshold_percentile="Top 25% (75th Percentile TMDB Popularity Threshold)",
        confidence_level=confidence,
        model_architecture=model_name,
        input_features={
            "genres": payload.genres,
            "release_year": payload.release_year,
            "runtime": payload.runtime,
            "original_language": payload.original_language,
            "budget": payload.budget,
        },
        feature_insights=insights,
        poster_url=poster_url,
        tagline=payload.tagline,
        overview=payload.overview,
    )
    return response


def _log_predictions(payloads: List[MoviePredictionRequest], results: List[MoviePredictionResponse]) -> None:
    """Persist inferences for /api/analytics/summary. Best-effort: never raises."""
    try:
        prediction_store.log([
            {
                "title": r.title,
                "release_year": p.release_year,
                "runtime": p.runtime,
                "budget": p.budget,
                "original_language": p.original_language,
                "genres": p.genres,
                "probability": r.probability,
                "is_popular": r.is_popular,
                "model_architecture": r.model_architecture,
                "poster_url": r.poster_url,
            }
            for p, r in zip(payloads, results)
        ])
    except Exception as e:
        logger.warning(f"Prediction logging skipped: {e}")


@app.post("/api/predict", response_model=MoviePredictionResponse)
def predict_movie_popularity(payload: MoviePredictionRequest):
    prob = _mlp_probabilities([payload])[0]
    result = _build_prediction(payload, prob)
    _log_predictions([payload], [result])
    return result


# ==========================================
# [BE-3] HEAD-TO-HEAD COMPARATOR  ->  POST /api/compare
# ==========================================
class CompareRequest(BaseModel):
    movie_a: MoviePredictionRequest
    movie_b: MoviePredictionRequest


class CompareResponse(BaseModel):
    winner: str  # "movie_a" | "movie_b" | "tie"
    winner_title: Optional[str] = None
    probability_a: float
    probability_b: float
    delta_prob: float  # absolute gap |P(A) - P(B)|, 0.0 - 1.0
    margin: str  # "Tie" | "Narrow" | "Clear" | "Decisive"
    summary: str
    breakdown: Dict[str, Any]  # budget_efficiency, runtime_advantage, genre_synergy
    commentary: List[str]
    movie_a: MoviePredictionResponse
    movie_b: MoviePredictionResponse


# Same cross-genre affinities the MLP encodes in extract_cinephile_features().
_SYNERGY_RULES = [
    ("War + Drama", lambda g: {"war", "drama"} <= g),
    ("Science Fiction + Drama", lambda g: {"science fiction", "drama"} <= g),
    ("Romance + Drama", lambda g: {"romance", "drama"} <= g),
    ("Romance + Comedy", lambda g: {"romance", "comedy"} <= g),
    ("Crime + Thriller/Mystery/Drama/Music", lambda g: "crime" in g and bool(g & {"thriller", "mystery", "drama", "music"})),
    ("Action + Adventure + Science Fiction", lambda g: {"action", "adventure", "science fiction"} <= g),
    ("Animation + Fantasy/Adventure", lambda g: "animation" in g and bool(g & {"fantasy", "adventure"})),
    ("History + Drama", lambda g: {"history", "drama"} <= g),
]

BUDGET_FLOOR_USD = 1_000_000  # unreported/tiny budgets are floored so the ratio stays meaningful


def _side_label(side: str) -> str:
    return "Movie A" if side == "movie_a" else "Movie B"


def _genre_synergy(genres: List[str]) -> Dict[str, Any]:
    g = {x.strip().lower() for x in genres}
    matched = [name for name, rule in _SYNERGY_RULES if rule(g)]
    score = len(matched)
    label = "Strong" if score >= 2 else ("Moderate" if score == 1 else "None")
    return {"score": score, "rating": label, "matched": matched}


def _runtime_band(runtime: int) -> str:
    if runtime < 88:
        return "Short"
    if runtime <= 130:
        return "Standard"
    if runtime < 135:
        return "Extended"
    return "Epic"


def _compare_breakdown(a: MoviePredictionRequest, b: MoviePredictionRequest,
                       prob_a: float, prob_b: float) -> Dict[str, Any]:
    # --- Budget efficiency: popularity probability per $10M of budget ---
    eff_a = prob_a / (max(a.budget, BUDGET_FLOOR_USD) / 10_000_000)
    eff_b = prob_b / (max(b.budget, BUDGET_FLOOR_USD) / 10_000_000)
    if a.budget <= 0 and b.budget <= 0:
        b_leader = "tie"
        b_text = "Budget Efficiency: Neither film reports a budget, so efficiency cannot be compared."
    else:
        b_leader = "movie_a" if eff_a > eff_b else ("movie_b" if eff_b > eff_a else "tie")
        if b_leader == "tie":
            b_text = "Budget Efficiency: Both films convert budget into popularity probability at the same rate."
        else:
            hi, lo = (eff_a, eff_b) if b_leader == "movie_a" else (eff_b, eff_a)
            ratio = hi / lo if lo > 0 else float("inf")
            ratio_txt = f"{ratio:.1f}x" if ratio != float("inf") else "far"
            b_text = (
                f"Budget Efficiency: {_side_label(b_leader)} is {ratio_txt} more budget-efficient "
                f"(Movie A {eff_a:.2f} vs Movie B {eff_b:.2f} popularity probability per $10M, "
                f"budgets under ${BUDGET_FLOOR_USD:,} counted as ${BUDGET_FLOOR_USD:,})."
            )

    # --- Runtime advantage: bands the model encodes explicitly (Standard / Epic) ---
    band_a, band_b = _runtime_band(a.runtime), _runtime_band(b.runtime)
    favored = {"Standard", "Epic"}
    if band_a == band_b:
        r_leader = "tie"
        r_text = f"Runtime Advantage: Both run in the {band_a} band ({a.runtime}m vs {b.runtime}m), so neither has a pacing edge."
    elif band_a in favored and band_b not in favored:
        r_leader = "movie_a"
        r_text = f"Runtime Advantage: Movie A's {band_a} runtime ({a.runtime}m) fits a model-favored band, while Movie B's {band_b} runtime ({b.runtime}m) does not."
    elif band_b in favored and band_a not in favored:
        r_leader = "movie_b"
        r_text = f"Runtime Advantage: Movie B's {band_b} runtime ({b.runtime}m) fits a model-favored band, while Movie A's {band_a} runtime ({a.runtime}m) does not."
    elif band_a in favored and band_b in favored:
        r_leader = "tie"
        r_text = f"Runtime Advantage: Movie A is {band_a} ({a.runtime}m) and Movie B is {band_b} ({b.runtime}m); both are model-favored, so neither holds an inherent edge."
    else:
        r_leader = "tie"
        r_text = f"Runtime Advantage: Neither runtime ({a.runtime}m vs {b.runtime}m) sits in a model-favored band."

    # --- Genre synergy rating ---
    syn_a, syn_b = _genre_synergy(a.genres), _genre_synergy(b.genres)
    if syn_a["score"] == syn_b["score"]:
        g_leader = "tie"
        g_text = f"Genre Synergy: Equal rating ({syn_a['rating']} vs {syn_b['rating']}); neither lineup has more affinity pairings."
    else:
        g_leader = "movie_a" if syn_a["score"] > syn_b["score"] else "movie_b"
        win = syn_a if g_leader == "movie_a" else syn_b
        names = ", ".join(win["matched"])
        g_text = f"Genre Synergy: {_side_label(g_leader)} rates {win['rating']} ({syn_a['score']} vs {syn_b['score']} affinity pairings: {names})."

    return {
        "budget_efficiency": {
            "leader": b_leader,
            "movie_a": {"budget_usd": a.budget, "popularity_per_10m_usd": round(eff_a, 4)},
            "movie_b": {"budget_usd": b.budget, "popularity_per_10m_usd": round(eff_b, 4)},
            "commentary": b_text,
        },
        "runtime_advantage": {
            "leader": r_leader,
            "movie_a": {"runtime_minutes": a.runtime, "band": band_a},
            "movie_b": {"runtime_minutes": b.runtime, "band": band_b},
            "commentary": r_text,
        },
        "genre_synergy": {
            "leader": g_leader,
            "movie_a": syn_a,
            "movie_b": syn_b,
            "commentary": g_text,
        },
    }


@app.post("/api/compare", response_model=CompareResponse)
def compare_movies(payload: CompareRequest):
    a, b = payload.movie_a, payload.movie_b
    probs = _mlp_probabilities([a, b])  # single batched inference for both movies
    res_a, res_b = _build_prediction(a, probs[0]), _build_prediction(b, probs[1])
    _log_predictions([a, b], [res_a, res_b])

    prob_a, prob_b = res_a.probability, res_b.probability
    delta = round(abs(prob_a - prob_b), 4)
    if delta < 0.0001:
        winner, margin = "tie", "Tie"
    else:
        winner = "movie_a" if prob_a > prob_b else "movie_b"
        margin = "Narrow" if delta < 0.05 else ("Clear" if delta < 0.20 else "Decisive")
    winner_title = None if winner == "tie" else (res_a.title if winner == "movie_a" else res_b.title)

    breakdown = _compare_breakdown(a, b, prob_a, prob_b)
    commentary = [breakdown[k]["commentary"] for k in ("budget_efficiency", "runtime_advantage", "genre_synergy")]
    if winner == "tie":
        summary = f"'{res_a.title}' and '{res_b.title}' are tied at {prob_a:.1%} popularity probability."
    else:
        summary = (
            f"'{winner_title}' wins ({_side_label(winner)}) with {max(prob_a, prob_b):.1%} vs "
            f"{min(prob_a, prob_b):.1%} popularity probability — a {margin.lower()} margin of "
            f"{delta * 100:.1f} percentage points."
        )

    return CompareResponse(
        winner=winner,
        winner_title=winner_title,
        probability_a=prob_a,
        probability_b=prob_b,
        delta_prob=delta,
        margin=margin,
        summary=summary,
        breakdown=breakdown,
        commentary=commentary,
        movie_a=res_a,
        movie_b=res_b,
    )


# ==========================================
# [BE-4] PLATFORM INSIGHTS  ->  GET /api/analytics/summary
# ==========================================
@app.get("/api/analytics/summary")
def analytics_summary(
    min_probability: float = Query(0.5, ge=0.0, le=1.0, description="Predictions at/above this probability count as 'top-scoring' for the genre ranking"),
    top_genres: int = Query(5, ge=1, le=19, description="How many genres to return"),
):
    """Aggregated stats over logged predictions. Results are cached in memory (30s TTL, invalidated on every new prediction)."""
    return prediction_store.summary(min_probability=min_probability, top_genres=top_genres)
