"""
scoring.py — XGBoost + isotonic calibration scoring pipeline.

Mirrors the production Lambda scoring pipeline (ReCiter---Scoring/app/).
Loads pre-trained models and runs the full scoring chain:
  raw features → derived features → scaler → XGBoost → isotonic calibration → safety net
"""

import logging
from pathlib import Path
from typing import Dict, List

import joblib
import numpy as np
import pandas as pd

from core.preprocessing import (
    FEEDBACK_IDENTITY_BASE_FEATURES,
    FEEDBACK_IDENTITY_FEATURES,
    IDENTITY_ONLY_BASE_FEATURES,
    IDENTITY_ONLY_FEATURES,
    compute_derived_features_feedback_identity,
    compute_derived_features_identity_only,
)

_log = logging.getLogger(__name__)

_MODEL_DIR = Path(__file__).parent.parent / "models"

# Cache loaded models to avoid re-reading from disk
_model_cache: dict = {}


def _load_model_set(model_dir: str, model_type: str) -> dict:
    """Load model + scaler + calibrator from disk, with caching."""
    cache_key = f"{model_dir}/{model_type}"
    if cache_key in _model_cache:
        return _model_cache[cache_key]

    path = _MODEL_DIR / model_dir
    if not path.exists():
        raise FileNotFoundError(f"Model directory not found: {path}")

    prefix = "feedbackIdentity" if model_type == "feedback" else "identityOnly"
    models = {
        "model": joblib.load(path / f"{prefix}Model.joblib"),
        "scaler": joblib.load(path / f"{prefix}Scaler.joblib"),
        "calibrator": joblib.load(path / f"{prefix}Calibrator.joblib"),
    }

    if hasattr(models["model"], "n_jobs"):
        models["model"].set_params(n_jobs=1)

    _log.info(f"Loaded {prefix} model from {path}")
    _model_cache[cache_key] = models
    return models


def score_articles(
    feature_rows: List[Dict],
    curated: Dict[str, str],
    model_dir: str = "wcm",
    identity_first_name: str = "",
) -> pd.DataFrame:
    """
    Full scoring pipeline matching production Lambda behavior.

    Args:
        feature_rows: List of dicts, each with base feature values + pmid.
        curated: Dict mapping pmid → 'ACCEPTED'/'REJECTED' for feedback counts.
        model_dir: 'wcm' or 'local'.
        identity_first_name: For name frequency scoring (passed via DataFrame).

    Returns:
        DataFrame with pmid, all features, raw_score, calibrated_score (0-1 scale).
    """
    if not feature_rows:
        return pd.DataFrame()

    df = pd.DataFrame(feature_rows)

    has_feedback = bool(curated) and any(curated.values())
    if has_feedback:
        count_accepted = sum(1 for v in curated.values() if v == "ACCEPTED")
        count_rejected = sum(1 for v in curated.values() if v == "REJECTED")
        df["countAccepted"] = count_accepted
        df["countRejected"] = count_rejected

    if identity_first_name:
        df["identityFirstName"] = identity_first_name

    if has_feedback:
        # --- Feedback model scoring ---
        fb_models = _load_model_set(model_dir, "feedback")

        # Ensure all base features exist
        for feat in FEEDBACK_IDENTITY_BASE_FEATURES:
            if feat not in df.columns:
                df[feat] = 0
            df[feat] = df[feat].fillna(0)

        df_fb = compute_derived_features_feedback_identity(df.copy())

        X_fb = fb_models["scaler"].transform(df_fb[FEEDBACK_IDENTITY_FEATURES].values)
        raw_fb = fb_models["model"].predict_proba(X_fb)[:, 1]
        cal_fb = fb_models["calibrator"].predict(raw_fb)
        score_fb = cal_fb * 100

        # --- Identity-only safety net ---
        # Cap feedback score at io_score * 33 to prevent feedback features
        # from overriding strong identity-based rejection
        io_models = _load_model_set(model_dir, "identity")

        df_io = df.copy()
        for feat in IDENTITY_ONLY_BASE_FEATURES:
            if feat not in df_io.columns:
                df_io[feat] = 0
            df_io[feat] = df_io[feat].fillna(0)

        df_io = compute_derived_features_identity_only(df_io)

        X_io = io_models["scaler"].transform(df_io[IDENTITY_ONLY_FEATURES].values)
        raw_io = io_models["model"].predict_proba(X_io)[:, 1]
        cal_io = io_models["calibrator"].predict(raw_io)
        score_io = cal_io * 100
        score_cap = score_io * 33

        n_capped = int(np.sum(score_fb > score_cap))
        if n_capped > 0:
            _log.info(f"Safety net: capping {n_capped} articles where fb > io*33")
        score_fb = np.minimum(score_fb, score_cap)

        df_fb["raw_score"] = raw_fb
        df_fb["calibrated_score"] = np.clip(score_fb / 100, 0.0, 1.0)
        return df_fb

    else:
        # --- Identity-only model scoring ---
        io_models = _load_model_set(model_dir, "identity")

        for feat in IDENTITY_ONLY_BASE_FEATURES:
            if feat not in df.columns:
                df[feat] = 0
            df[feat] = df[feat].fillna(0)

        df_io = compute_derived_features_identity_only(df.copy())

        X_io = io_models["scaler"].transform(df_io[IDENTITY_ONLY_FEATURES].values)
        raw_io = io_models["model"].predict_proba(X_io)[:, 1]
        cal_io = io_models["calibrator"].predict(raw_io)
        score_io = cal_io * 100

        df_io["raw_score"] = raw_io
        df_io["calibrated_score"] = np.clip(score_io / 100, 0.0, 1.0)
        return df_io
