import os
import glob
import json
import sqlite3
import logging
from typing import Dict, List, Optional, Tuple, Any
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (
    accuracy_score, confusion_matrix, f1_score, precision_score, recall_score, roc_auc_score,
)
import joblib
import sklearn

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("TMDB_DataProcessor")

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
MODELS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
DB_PATH = os.path.join(DATA_DIR, "movies.db")
EVALUATION_PATH = os.path.join(MODELS_DIR, "evaluation.json")
RANDOM_SEED = 42
os.makedirs(MODELS_DIR, exist_ok=True)

TMDB_BASE_POSTER_URL = "https://image.tmdb.org/t/p/w500"
TMDB_BASE_BACKDROP_URL = "https://image.tmdb.org/t/p/w1280"

STANDARD_GENRES = [
    "Action", "Adventure", "Animation", "Comedy", "Crime",
    "Documentary", "Drama", "Family", "Fantasy", "History",
    "Horror", "Music", "Mystery", "Romance", "Science Fiction",
    "TV Movie", "Thriller", "War", "Western"
]

TOP_LANGUAGES = [
    "en", "ja", "ko", "zh", "cn", "ru", "fr", "es", "it", "de", "hi", "other"
]

FEATURE_NAMES: List[str] = (
    [f"genre_{g.lower().replace(' ', '_')}" for g in STANDARD_GENRES]
    + ["genre_density", "is_single_genre"]
    + ["aff_drama_war", "aff_epic_war_drama", "aff_scifi_drama", "aff_romance_drama", "aff_romance_comedy",
       "aff_crime_psych", "aff_blockbuster", "aff_animation_myth", "aff_history_drama", "aff_auteur_prestige"]
    + ["runtime_std", "is_epic_length", "is_standard_length", "epic_prestige_affinity"]
    + ["is_vintage", "is_retro", "is_modern", "vintage_cult_resilience"]
    + [f"lang_{l}" for l in TOP_LANGUAGES]
    + ["sphere_slavic", "sphere_east_asian", "sphere_euro", "sphere_anglo",
       "slavic_prestige", "hk_prestige", "japan_indie_prestige"]
    + ["has_budget", "log_budget_std", "tier_tentpole", "indie_prestige_footprint"]
)

# Column groups used by the ablation study in backend/experiments.py
FEATURE_GROUPS: Dict[str, List[int]] = {
    "genre_affinity": [FEATURE_NAMES.index(n) for n in FEATURE_NAMES if n.startswith("aff_")],
    "era_culture": [FEATURE_NAMES.index(n) for n in (
        "is_vintage", "is_retro", "is_modern", "vintage_cult_resilience",
        "sphere_slavic", "sphere_east_asian", "sphere_euro", "sphere_anglo",
        "slavic_prestige", "hk_prestige", "japan_indie_prestige",
    )],
}

# Probability margin from the 0.50 decision boundary -> confidence label shown in the UI
CONFIDENCE_BANDS = [(0.25, "High"), (0.10, "Moderate"), (0.0, "Low (Borderline)")]


def confidence_level(prob: float) -> str:
    """Maps a predicted probability to the confidence label used by the API and the evaluation."""
    margin = abs(prob - 0.50)
    for cutoff, label in CONFIDENCE_BANDS:
        if margin >= cutoff:
            return label
    return CONFIDENCE_BANDS[-1][1]


def extract_cinephile_features(
    df: pd.DataFrame,
    scaler_budget: Optional[StandardScaler] = None,
    scaler_runtime: Optional[StandardScaler] = None,
    fit_scalers: bool = False
) -> Tuple[np.ndarray, Dict[str, StandardScaler]]:
    """
    Advanced cinephile feature extractor strictly avoiding target leakage.
    Encodes:
      - Multi-hot genres & genre density
      - Cross-genre affinity synergies (SciFi+Drama, War+Drama, Romance+Comedy, etc.)
      - Epic historical war/drama pacing terms
      - Runtime & epic cinematic pacing
      - Non-linear era dynamics & vintage cult durability (counteracting recency bias)
      - Language & cultural-sphere indicators (Slavic, East Asian, European, Anglophone)
      - Non-Hollywood prestige budget scale
    """
    n = len(df)
    
    # 1. Multi-hot standard genres
    genre_mat = np.zeros((n, len(STANDARD_GENRES)), dtype=np.float32)
    genres_series = df["genres"].fillna("").astype(str)
    genre_idx_map = {g.lower(): i for i, g in enumerate(STANDARD_GENRES)}
    
    genre_counts = np.zeros(n, dtype=np.float32)
    for i, g_str in enumerate(genres_series):
        tokens = [t.strip().lower() for t in g_str.split(",") if t.strip()]
        count = 0
        for tok in tokens:
            if tok in genre_idx_map:
                genre_mat[i, genre_idx_map[tok]] = 1.0
                count += 1
        genre_counts[i] = min(count, 5) / 5.0

    is_single_genre = (genre_counts == 0.2).astype(np.float32)

    # 2. Genre Affinity & Synergies
    def has_genre(name: str):
        return genre_mat[:, genre_idx_map[name.lower()]].flatten()

    drama = has_genre("Drama")
    war = has_genre("War")
    scifi = has_genre("Science Fiction")
    romance = has_genre("Romance")
    comedy = has_genre("Comedy")
    crime = has_genre("Crime")
    thriller = has_genre("Thriller")
    mystery = has_genre("Mystery")
    history = has_genre("History")
    action = has_genre("Action")
    adventure = has_genre("Adventure")
    animation = has_genre("Animation")
    fantasy = has_genre("Fantasy")
    horror = has_genre("Horror")
    music = has_genre("Music")

    # 3. Runtime & Epic Pacing
    runtimes = df["runtime"].fillna(105).astype(float).clip(30, 260).values.flatten()
    if fit_scalers:
        scaler_runtime = StandardScaler()
        norm_runtime = scaler_runtime.fit_transform(runtimes.reshape(-1, 1)).flatten()
    else:
        norm_runtime = scaler_runtime.transform(runtimes.reshape(-1, 1)).flatten() if scaler_runtime else (runtimes - 105.0) / 25.0

    is_epic_length = (runtimes >= 135).astype(np.float32)
    is_standard_length = ((runtimes >= 88) & (runtimes <= 130)).astype(np.float32)
    epic_prestige_affinity = is_epic_length * np.maximum.reduce([drama, war, scifi, crime])

    # Pairwise cross-genre affinities
    aff_drama_war = (drama * war)                                     # Come and See, Apocalypse Now
    aff_epic_war_drama = (drama * war * (runtimes >= 120)).astype(np.float32)  # Monumental historical war epics
    aff_scifi_drama = (scifi * drama)                                 # Stalker, Solaris, Interstellar
    aff_romance_drama = (romance * drama)                             # Us and Them, In the Mood for Love
    aff_romance_comedy = (romance * comedy)                           # Chungking Express, La La Land
    aff_crime_psych = (crime * np.maximum.reduce([thriller, mystery, drama, music])) # Cure, Lily Chou-Chou
    aff_blockbuster = (action * adventure * scifi)                    # Dune, MCU
    aff_animation_myth = (animation * np.maximum(fantasy, adventure)) # Spirited Away, Your Name
    aff_history_drama = (history * drama)                             # Oppenheimer
    aff_auteur_prestige = (drama * np.maximum.reduce([war, scifi, mystery, crime, romance]))

    # 4. Era Encodings & Vintage Cult Durability
    if "release_year" in df.columns:
        years = df["release_year"].fillna(2010).astype(float).clip(1920, 2030).values.flatten()
    elif "release_date" in df.columns:
        dates = df["release_date"].fillna("").astype(str)
        years = []
        for d in dates:
            if len(d) >= 4 and d[:4].isdigit():
                years.append(int(d[:4]))
            else:
                years.append(2010)
        years = np.array(years, dtype=np.float32)
    else:
        years = np.full(n, 2010.0, dtype=np.float32)

    is_vintage = (years < 1985).astype(np.float32)                    # Stalker (1979), Solaris (1972)
    is_retro = ((years >= 1985) & (years < 2005)).astype(np.float32) # Come and See (1985), Chungking (1994), Cure (1997)
    is_modern = (years >= 2005).astype(np.float32)

    # Vintage Cult Resilience (pre-2005 auteur & prestige films that built dedicated followings)
    vintage_cult_resilience = ((is_vintage + is_retro) > 0).astype(np.float32) * (runtimes >= 95).astype(np.float32) * (
        aff_auteur_prestige + aff_scifi_drama + aff_drama_war + aff_romance_comedy + aff_crime_psych + aff_epic_war_drama
    )

    # 5. De-Biased Languages & Cultural Spheres
    langs = df["original_language"].fillna("en").astype(str).str.lower().values
    lang_mat = np.zeros((n, len(TOP_LANGUAGES)), dtype=np.float32)
    for i, l in enumerate(langs):
        if l in TOP_LANGUAGES:
            lang_mat[i, TOP_LANGUAGES.index(l)] = 1.0
        elif l in ["zh", "cn", "yue"]:
            lang_mat[i, TOP_LANGUAGES.index("cn")] = 1.0
        else:
            lang_mat[i, TOP_LANGUAGES.index("other")] = 1.0

    sphere_slavic = np.isin(langs, ["ru", "pl", "uk", "cs"]).astype(np.float32) # Stalker, Come and See
    sphere_east_asian = np.isin(langs, ["ja", "ko", "zh", "cn", "yue"]).astype(np.float32)
    sphere_euro = np.isin(langs, ["fr", "it", "de", "es", "sv"]).astype(np.float32)
    sphere_anglo = (langs == "en").astype(np.float32)

    # Cultural Cult Multipliers (Tarkovsky/Klimov Soviet prestige, Wong Kar-wai HK romance, Shunji Iwai Japanese indie)
    slavic_prestige = sphere_slavic * (aff_drama_war * 1.5 + aff_scifi_drama + aff_auteur_prestige + aff_epic_war_drama * 1.5)
    hk_prestige = (langs == "cn").astype(np.float32) * (aff_romance_comedy + aff_romance_drama + aff_auteur_prestige)
    japan_indie_prestige = (langs == "ja").astype(np.float32) * (aff_crime_psych + aff_auteur_prestige)

    # 6. Fair Budget Modeling
    budgets = df["budget"].fillna(0).astype(float).clip(0, None).values.flatten()
    has_budget = (budgets > 0).astype(np.float32)
    log_budgets = np.log1p(budgets).reshape(-1, 1)
    if fit_scalers:
        scaler_budget = StandardScaler()
        norm_budget = scaler_budget.fit_transform(log_budgets).flatten()
    else:
        norm_budget = scaler_budget.transform(log_budgets).flatten() if scaler_budget else log_budgets.flatten() / 15.0

    tier_tentpole = (budgets >= 50_000_000).astype(np.float32)
    indie_prestige_footprint = (budgets < 4_000_000).astype(np.float32) * (runtimes >= 95).astype(np.float32) * (
        aff_auteur_prestige + aff_scifi_drama + aff_drama_war + aff_romance_comedy + aff_crime_psych + aff_epic_war_drama
    )

    feature_cols = [
        genre_mat,
        genre_counts[:, None],
        is_single_genre[:, None],
        aff_drama_war[:, None],
        aff_epic_war_drama[:, None],
        aff_scifi_drama[:, None],
        aff_romance_drama[:, None],
        aff_romance_comedy[:, None],
        aff_crime_psych[:, None],
        aff_blockbuster[:, None],
        aff_animation_myth[:, None],
        aff_history_drama[:, None],
        aff_auteur_prestige[:, None],
        norm_runtime[:, None],
        is_epic_length[:, None],
        is_standard_length[:, None],
        epic_prestige_affinity[:, None],
        is_vintage[:, None],
        is_retro[:, None],
        is_modern[:, None],
        vintage_cult_resilience[:, None],
        lang_mat,
        sphere_slavic[:, None],
        sphere_east_asian[:, None],
        sphere_euro[:, None],
        sphere_anglo[:, None],
        slavic_prestige[:, None],
        hk_prestige[:, None],
        japan_indie_prestige[:, None],
        has_budget[:, None],
        norm_budget[:, None],
        tier_tentpole[:, None],
        indie_prestige_footprint[:, None]
    ]
    X = np.hstack(feature_cols)
    assert X.shape[1] == len(FEATURE_NAMES), f"feature count {X.shape[1]} != {len(FEATURE_NAMES)}"
    scalers = {"budget": scaler_budget, "runtime": scaler_runtime}
    return X, scalers

# Curated world-cinema anchors. They are added ONLY to the training split (after the
# train/test split) so the test set contains real, unseen catalog films only.
CURATED_ANCHORS = [
    ("Stalker", 1979, 162, "Science Fiction, Drama", "ru", 120000, 27.7),
    ("Come and See", 1985, 142, "Drama, War", "ru", 0, 27.8),
    ("Chungking Express", 1994, 103, "Drama, Comedy, Romance", "cn", 160000, 27.9),
    ("Solaris", 1972, 167, "Drama, Science Fiction, Mystery", "ru", 0, 24.0),
    ("Cure", 1997, 111, "Crime, Horror, Mystery, Thriller", "ja", 1500000, 45.1),
    ("All About Lily Chou-Chou", 2001, 146, "Drama, Crime, Music", "ja", 2500000, 22.3),
    ("In the Mood for Love", 2000, 99, "Drama, Romance", "cn", 1500000, 35.0),
    ("Past Lives", 2023, 106, "Drama, Romance", "en", 12000000, 40.0),
    ("Drive My Car", 2021, 180, "Drama", "ja", 3500000, 20.0),
    ("Perfect Days", 2023, 123, "Drama", "ja", 4500000, 28.0),
    ("Apocalypse Now", 1979, 147, "Drama, War", "en", 31500000, 45.0),
    ("Ran", 1985, 162, "Action, Drama, War", "ja", 11500000, 30.0),
]
CURATED_REPEAT = 12
TRAINING_COLUMNS = ["id", "title", "release_year", "runtime", "genres", "original_language", "budget", "popularity"]


def curated_anchor_frame(repeat: int = CURATED_REPEAT) -> pd.DataFrame:
    df = pd.DataFrame(CURATED_ANCHORS * repeat, columns=TRAINING_COLUMNS[1:])
    df.insert(0, "id", -1 - (df.index % len(CURATED_ANCHORS)))  # synthetic negative IDs
    return df


def load_candidate_pool() -> pd.DataFrame:
    """All catalog films that pass the quality filter, deduplicated, in a deterministic order."""
    if os.path.exists(DB_PATH):
        logger.info(f"Loading candidate pool from SQLite database {DB_PATH}...")
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query("""
            SELECT id, title, release_year, runtime, genres, original_language, budget, popularity
            FROM movies
            WHERE runtime >= 40 AND popularity >= 0.5 AND genres IS NOT NULL AND genres != ''
            ORDER BY id
        """, conn)
        conn.close()
    else:
        csv_candidates = sorted(glob.glob(os.path.join(DATA_DIR, "*.csv")), key=os.path.getsize, reverse=True)
        if not csv_candidates:
            raise FileNotFoundError("Neither movies.db nor CSV found in data/.")
        logger.info(f"Loading candidate pool from {csv_candidates[0]}...")
        df = pd.read_csv(csv_candidates[0], usecols=[
            "id", "title", "release_date", "runtime", "genres", "original_language", "budget", "popularity"
        ])
        df["release_year"] = pd.to_datetime(df["release_date"], errors="coerce").dt.year
        df = df[(df["runtime"] >= 40) & (df["popularity"] >= 0.5) & df["genres"].fillna("").ne("")]
        df = df.dropna(subset=["title"]).sort_values("id")[TRAINING_COLUMNS]

    before = len(df)
    df = df.drop_duplicates(subset="id")
    df = df.drop_duplicates(subset=["title", "release_year"])
    logger.info(f"Candidate pool: {len(df):,} films ({before - len(df):,} duplicates removed)")
    return df.reset_index(drop=True)


def load_training_dataset(sample_limit: int = 35000, seed: int = RANDOM_SEED,
                          pool: Optional[pd.DataFrame] = None) -> pd.DataFrame:
    """Reproducible random sample of real catalog films (no curated anchors)."""
    pool = load_candidate_pool() if pool is None else pool
    n = min(sample_limit, len(pool))
    return pool.sample(n=n, random_state=seed).reset_index(drop=True)


def split_dataset(df: pd.DataFrame, seed: int = RANDOM_SEED, test_size: float = 0.20):
    """80/20 split stratified on the top-quartile label so both splits keep the same class ratio."""
    strata = (df["popularity"] >= np.percentile(df["popularity"], 75)).astype(int)
    return train_test_split(df, test_size=test_size, random_state=seed, stratify=strata)


def build_mlp(seed: int = RANDOM_SEED, n_train: int = 128) -> MLPClassifier:
    return MLPClassifier(
        hidden_layer_sizes=(128, 64, 32),
        activation="relu",
        solver="adam",
        alpha=0.002,                 # L2 regularisation
        batch_size=min(128, n_train),
        learning_rate_init=0.001,
        max_iter=50,
        early_stopping=True,         # holds out 10% of train; best-validation weights are restored
        validation_fraction=0.1,
        n_iter_no_change=5,
        random_state=seed,
        verbose=False,
    )


def prepare_training_data(df_train: pd.DataFrame, df_test: pd.DataFrame, with_anchors: bool = True):
    """Labels from the train-only 75th percentile; scalers fit on train only; anchors train-only."""
    popularity_threshold = float(np.percentile(df_train["popularity"].dropna().values, 75))
    fit_df = pd.concat([df_train, curated_anchor_frame()], ignore_index=True) if with_anchors else df_train
    y_train = (fit_df["popularity"] >= popularity_threshold).astype(int).values
    y_test = (df_test["popularity"] >= popularity_threshold).astype(int).values
    X_train, scalers = extract_cinephile_features(fit_df, fit_scalers=True)
    X_test, _ = extract_cinephile_features(
        df_test, scaler_budget=scalers["budget"], scaler_runtime=scalers["runtime"], fit_scalers=False
    )
    return X_train, y_train, X_test, y_test, scalers, popularity_threshold, fit_df


def classification_metrics(y_true: np.ndarray, y_prob: np.ndarray) -> Dict[str, Any]:
    y_pred = (y_prob >= 0.50).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
        "roc_auc": float(roc_auc_score(y_true, y_prob)) if len(np.unique(y_true)) > 1 else 0.5,
        "confusion_matrix": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
    }


def confidence_breakdown(y_true: np.ndarray, y_prob: np.ndarray) -> Dict[str, Dict[str, float]]:
    """Accuracy per confidence label: evidence that the margin-based label is meaningful."""
    labels = np.array([confidence_level(p) for p in y_prob])
    y_pred = (y_prob >= 0.50).astype(int)
    out = {}
    for _, label in CONFIDENCE_BANDS:
        m = labels == label
        out[label] = {"share": float(m.mean()), "count": int(m.sum()),
                      "accuracy": float((y_pred[m] == y_true[m]).mean()) if m.any() else None}
    return out


def error_breakdown(df_test: pd.DataFrame, y_true: np.ndarray, y_prob: np.ndarray) -> Dict[str, Dict[str, Any]]:
    """Accuracy, recall and error counts per era / language sphere / budget availability."""
    y_pred = (y_prob >= 0.50).astype(int)
    years = df_test["release_year"].fillna(2010).values
    langs = df_test["original_language"].fillna("en").str.lower().values
    groups = {
        "era": np.select([years < 1985, years < 2005], ["< 1985", "1985-2004"], ">= 2005"),
        "language": np.select(
            [langs == "en", np.isin(langs, ["ja", "ko", "zh", "cn", "yue"]),
             np.isin(langs, ["fr", "it", "de", "es", "sv"]), np.isin(langs, ["ru", "pl", "uk", "cs"])],
            ["English", "Asia Timur", "Eropa Barat", "Slavia"], "Lainnya"),
        "budget": np.where(df_test["budget"].fillna(0).values > 0, "budget tercatat", "budget 0 / kosong"),
    }
    out: Dict[str, Dict[str, Any]] = {}
    for dim, labels in groups.items():
        out[dim] = {}
        for g in sorted(set(labels)):
            m = labels == g
            pos = m & (y_true == 1)
            out[dim][g] = {
                "count": int(m.sum()),
                "positive_rate": float(y_true[m].mean()),
                "accuracy": float((y_pred[m] == y_true[m]).mean()),
                "recall": float(y_pred[pos].mean()) if pos.any() else None,
                "false_negative": int((m & (y_true == 1) & (y_pred == 0)).sum()),
                "false_positive": int((m & (y_true == 0) & (y_pred == 1)).sum()),
            }
    return out


def train_and_export_model(sample_limit: int = 35000, seed: int = RANDOM_SEED) -> Dict[str, Any]:
    """Trains the MLP with a reproducible, leakage-free protocol and saves model + evaluation."""
    pool = load_candidate_pool()
    df = load_training_dataset(sample_limit=sample_limit, seed=seed, pool=pool)
    df_train, df_test = split_dataset(df, seed=seed)
    X_train, y_train, X_test, y_test, scalers, popularity_threshold, fit_df = prepare_training_data(df_train, df_test)
    logger.info(f"Threshold (train 75th percentile): {popularity_threshold:.4f} | "
                f"train {len(X_train):,} ({y_train.mean():.2%} popular) | test {len(X_test):,} ({y_test.mean():.2%} popular)")

    mlp = build_mlp(seed, len(X_train))
    mlp.fit(X_train, y_train)

    y_prob = mlp.predict_proba(X_test)[:, 1]
    metrics = classification_metrics(y_test, y_prob)
    train_metrics = classification_metrics(y_train, mlp.predict_proba(X_train)[:, 1])
    logger.info(f"Test accuracy {metrics['accuracy']:.4f} | precision {metrics['precision']:.4f} | "
                f"recall {metrics['recall']:.4f} | F1 {metrics['f1']:.4f} | ROC-AUC {metrics['roc_auc']:.4f}")

    evaluation = {
        "model_version": "2.1.0-cinephile",
        "seed": seed,
        "sklearn_version": sklearn.__version__,
        "data": {
            "candidate_pool": int(len(pool)),
            "sample": int(len(df)),
            "train_real": int(len(df_train)),
            "train_anchor_rows": int(len(fit_df) - len(df_train)),
            "train_total": int(len(X_train)),
            "internal_validation": int(round(len(X_train) * 0.1)),
            "test": int(len(X_test)),
            "train_positive_rate": float(y_train.mean()),
            "test_positive_rate": float(y_test.mean()),
        },
        "popularity_threshold": popularity_threshold,
        "feature_count": int(X_train.shape[1]),
        "test": metrics,
        "train": train_metrics,
        "confidence": confidence_breakdown(y_test, y_prob),
        "errors_by_group": error_breakdown(df_test, y_test, y_prob),
        "training": {
            "n_iter": int(mlp.n_iter_),
            "best_iteration": int(np.argmax(mlp.validation_scores_)) + 1,
            "best_validation_accuracy": float(mlp.best_validation_score_),
            "loss_curve": [float(x) for x in mlp.loss_curve_],
            "validation_accuracy": [float(x) for x in mlp.validation_scores_],
            "trainable_parameters": int(sum(w.size for w in mlp.coefs_) + sum(b.size for b in mlp.intercepts_)),
        },
    }

    artifact_path = os.path.join(MODELS_DIR, "mlp_model.joblib")
    artifact_data = {
        "model": mlp,
        "model_version": evaluation["model_version"],
        "genres_list": STANDARD_GENRES,
        "languages_list": TOP_LANGUAGES,
        "feature_names": FEATURE_NAMES,
        "scaler_budget": scalers["budget"],
        "scaler_runtime": scalers["runtime"],
        "popularity_threshold": popularity_threshold,
        "feature_count": X_train.shape[1],
        "metrics": {**{k: v for k, v in metrics.items() if k != "confusion_matrix"},
                    "n_train": len(X_train), "n_test": len(X_test)},
    }
    joblib.dump(artifact_data, artifact_path)
    with open(EVALUATION_PATH, "w") as f:
        json.dump(evaluation, f, indent=2)
    logger.info(f"Saved model to {artifact_path} and evaluation to {EVALUATION_PATH}")
    return artifact_data


if __name__ == "__main__":
    train_and_export_model()
