"""Scenario comparison for the report (Bagian A, 6d): ablations, hyperparameters, baselines.

Every scenario reuses the exact training protocol of ``backend/data_processor.py``
(deduplicated pool, seeded sample, stratified 80/20 split, train-only threshold,
scalers and curated anchors) and is repeated over several seeds.

    backend/.venv/bin/python -m backend.experiments

Writes ``backend/models/experiments.json``. The deployed model is not modified.
"""
import json
import logging
import os
import sqlite3
import warnings
from typing import Any, Callable, Dict, List

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.neural_network import MLPClassifier

from backend.data_processor import (
    DB_PATH, FEATURE_GROUPS, MODELS_DIR, RANDOM_SEED, build_mlp, classification_metrics,
    curated_anchor_frame, extract_cinephile_features, load_candidate_pool, load_training_dataset,
    prepare_training_data, split_dataset,
)

warnings.filterwarnings("ignore")
logging.getLogger("TMDB_DataProcessor").setLevel(logging.WARNING)

SEEDS = [RANDOM_SEED, 7, 11, 99, 2024]
OUTPUT_PATH = os.path.join(MODELS_DIR, "experiments.json")
METRICS = ("accuracy", "precision", "recall", "f1", "roc_auc")


def _drop(X: np.ndarray, cols: List[int]) -> np.ndarray:
    return np.delete(X, cols, axis=1)


def _fit_eval(model, X_train, y_train, X_test, y_test) -> Dict[str, Any]:
    model.fit(X_train, y_train)
    out = classification_metrics(y_test, model.predict_proba(X_test)[:, 1])
    if isinstance(model, MLPClassifier):
        out["n_iter"] = int(model.n_iter_)
    return out


def standard(seed: int, pool: pd.DataFrame, *, drop: List[int] = None, model_fn: Callable = None,
             with_anchors: bool = True) -> Dict[str, Any]:
    df = load_training_dataset(seed=seed, pool=pool)
    tr, te = split_dataset(df, seed=seed)
    X_train, y_train, X_test, y_test, *_ = prepare_training_data(tr, te, with_anchors=with_anchors)
    if drop:
        X_train, X_test = _drop(X_train, drop), _drop(X_test, drop)
    model = model_fn(seed, len(X_train)) if model_fn else build_mlp(seed, len(X_train))
    return _fit_eval(model, X_train, y_train, X_test, y_test)


def majority(seed: int, pool: pd.DataFrame) -> Dict[str, Any]:
    df = load_training_dataset(seed=seed, pool=pool)
    tr, te = split_dataset(df, seed=seed)
    *_, y_test, _, _, _ = prepare_training_data(tr, te)
    return classification_metrics(y_test, np.zeros(len(y_test)))


def legacy_protocol(seed: int, pool: pd.DataFrame) -> Dict[str, Any]:
    """The v2.0 protocol: anchors x12 added BEFORE an unstratified split (they leak into test)."""
    df = pd.concat([load_training_dataset(seed=seed, pool=pool), curated_anchor_frame()], ignore_index=True)
    tr, te = train_test_split(df, test_size=0.20, random_state=seed)
    X_train, y_train, X_test, y_test, *_ = prepare_training_data(tr, te, with_anchors=False)
    out = _fit_eval(build_mlp(seed, len(X_train)), X_train, y_train, X_test, y_test)
    anchors_test = te["id"] < 0
    out["anchor_rows_in_test"] = int(anchors_test.sum())
    out["anchor_titles_in_train_and_test"] = int(len(set(te.title[anchors_test]) & set(tr.title[tr["id"] < 0])))
    return out


def with_engagement_leak(seed: int, pool: pd.DataFrame) -> Dict[str, Any]:
    """Adds vote_count / vote_average as inputs to show why they are excluded (target leakage)."""
    conn = sqlite3.connect(DB_PATH)
    votes = pd.read_sql_query("SELECT id, vote_count, vote_average FROM movies", conn).set_index("id")
    conn.close()
    df = load_training_dataset(seed=seed, pool=pool)
    tr, te = split_dataset(df, seed=seed)
    X_train, y_train, X_test, y_test, _, _, fit_df = prepare_training_data(tr, te)

    def leak(frame: pd.DataFrame) -> np.ndarray:
        v = votes.reindex(frame["id"]).fillna(0)
        return np.column_stack([np.log1p(v["vote_count"].values), v["vote_average"].values / 10.0])

    # anchors have no vote data: give them the train median so they don't stand out
    lt = leak(fit_df)
    lt[fit_df["id"].values < 0] = np.median(lt[fit_df["id"].values >= 0], axis=0)
    mu, sd = lt.mean(0), lt.std(0) + 1e-9
    X_train = np.hstack([X_train, (lt - mu) / sd])
    X_test = np.hstack([X_test, (leak(te) - mu) / sd])
    return _fit_eval(build_mlp(seed, len(X_train)), X_train, y_train, X_test, y_test)


def mlp_variant(**params) -> Callable:
    def make(seed: int, n_train: int) -> MLPClassifier:
        m = build_mlp(seed, n_train)
        m.set_params(**params)
        return m
    return make


SCENARIOS = {
    "MLP final (128-64-32)": dict(fn=standard),
    "Tanpa fitur genre affinity": dict(fn=standard, drop=FEATURE_GROUPS["genre_affinity"]),
    "Tanpa fitur era & budaya": dict(fn=standard, drop=FEATURE_GROUPS["era_culture"]),
    "Tanpa anchor kurasi": dict(fn=standard, with_anchors=False),
    "MLP kecil (64-32)": dict(fn=standard, model_fn=mlp_variant(hidden_layer_sizes=(64, 32))),
    "MLP besar (256-128-64)": dict(fn=standard, model_fn=mlp_variant(hidden_layer_sizes=(256, 128, 64))),
    "alpha 0.0002 (L2 lemah)": dict(fn=standard, model_fn=mlp_variant(alpha=0.0002)),
    "alpha 0.02 (L2 kuat)": dict(fn=standard, model_fn=mlp_variant(alpha=0.02)),
    "Regresi logistik": dict(fn=standard, model_fn=lambda s, n: LogisticRegression(max_iter=2000)),
    "Baseline kelas mayoritas": dict(fn=majority),
    "Protokol lama v2.0 (anchor bocor)": dict(fn=legacy_protocol),
    "Dengan vote_count/vote_average (bocor)": dict(fn=with_engagement_leak),
}


def main() -> None:
    pool = load_candidate_pool()
    results: Dict[str, Any] = {"seeds": SEEDS, "scenarios": {}}
    for name, spec in SCENARIOS.items():
        spec = dict(spec)
        fn = spec.pop("fn")
        runs = [fn(seed, pool, **spec) for seed in SEEDS]
        summary = {m: {"mean": float(np.mean([r[m] for r in runs])), "std": float(np.std([r[m] for r in runs]))}
                   for m in METRICS}
        results["scenarios"][name] = {"summary": summary, "runs": runs}
        print(f"{name:42s} " + "  ".join(f"{m} {summary[m]['mean']:.4f}±{summary[m]['std']:.4f}" for m in METRICS),
              flush=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(results, f, indent=2)
    print(f"Saved {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
