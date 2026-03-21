"""
scoring.py — XGBoost + isotonic calibration scoring pipeline.

Loads pre-trained models and runs the full scoring chain:
  raw features → derived features → scaler → XGBoost → isotonic calibration
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import joblib
import numpy as np
import pandas as pd

from core.preprocessing import (
    FEEDBACK_IDENTITY_BASE_FEATURES,
    FEEDBACK_IDENTITY_FEATURES,
    IDENTITY_ONLY_BASE_FEATURES,
    IDENTITY_ONLY_FEATURES,
    preprocess_for_inference_feedback_identity,
    preprocess_for_inference_identity_only,
)

_log = logging.getLogger(__name__)

_MODEL_DIR = Path(__file__).parent.parent / "models"


class ScoringModel:
    """Wraps XGBoost model + StandardScaler + IsotonicRegression calibrator."""

    def __init__(self, model_path: Path, model_type: str):
        """
        Args:
            model_path: Directory containing model files.
            model_type: 'feedbackIdentity' or 'identityOnly'
        """
        self.model_type = model_type
        self.model = joblib.load(model_path / f"{model_type}Model.joblib")
        self.scaler = joblib.load(model_path / f"{model_type}Scaler.joblib")
        self.calibrator = joblib.load(model_path / f"{model_type}Calibrator.joblib")

        if model_type == "feedbackIdentity":
            self.base_features = FEEDBACK_IDENTITY_BASE_FEATURES
            self.all_features = FEEDBACK_IDENTITY_FEATURES
            self.preprocess_fn = preprocess_for_inference_feedback_identity
        else:
            self.base_features = IDENTITY_ONLY_BASE_FEATURES
            self.all_features = IDENTITY_ONLY_FEATURES
            self.preprocess_fn = preprocess_for_inference_identity_only

        _log.info(f"Loaded {model_type} model from {model_path}")

    def predict(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Run full prediction pipeline.

        Args:
            df: DataFrame with at least the base feature columns.

        Returns:
            DataFrame with added columns: raw_score, calibrated_score
        """
        df = self.preprocess_fn(df)

        # Use only the features the scaler was trained with.
        # Production WCM models were trained without firstNameFrequencyScore;
        # locally trained models may include it.
        n_expected = self.scaler.n_features_in_
        features_to_use = self.all_features[:n_expected]
        feature_df = df[features_to_use].copy()
        scaled = self.scaler.transform(feature_df)

        raw_probs = self.model.predict_proba(scaled)[:, 1]
        calibrated = self.calibrator.predict(raw_probs)

        df = df.copy()
        df["raw_score"] = raw_probs
        df["calibrated_score"] = np.clip(calibrated, 0.0, 1.0)
        return df


def load_model(model_dir: str = "wcm", model_type: str = "feedbackIdentity") -> ScoringModel:
    """Load a scoring model.

    Args:
        model_dir: 'wcm' or 'local'
        model_type: 'feedbackIdentity' or 'identityOnly'
    """
    path = _MODEL_DIR / model_dir
    if not path.exists():
        raise FileNotFoundError(f"Model directory not found: {path}")
    return ScoringModel(path, model_type)


def score_articles(
    feature_rows: List[Dict],
    curated: Dict[int, str],
    model_dir: str = "wcm",
    identity_first_name: str = "",
) -> pd.DataFrame:
    """
    Full scoring pipeline: takes computed feature dicts, returns scored DataFrame.

    Args:
        feature_rows: List of dicts, each with base feature values + pmid.
        curated: Dict mapping pmid → 'ACCEPTED'/'REJECTED' for feedback counts.
        model_dir: 'wcm' or 'local'.
        identity_first_name: For name frequency scoring.

    Returns:
        DataFrame with pmid, all features, raw_score, calibrated_score.
    """
    if not feature_rows:
        return pd.DataFrame()

    df = pd.DataFrame(feature_rows)

    has_feedback = any(curated.values())
    if has_feedback:
        count_accepted = sum(1 for v in curated.values() if v == "ACCEPTED")
        count_rejected = sum(1 for v in curated.values() if v == "REJECTED")
        df["countAccepted"] = count_accepted
        df["countRejected"] = count_rejected
        model_type = "feedbackIdentity"
    else:
        model_type = "identityOnly"

    if identity_first_name:
        df["identityFirstName"] = identity_first_name

    # Ensure all base features exist
    if model_type == "feedbackIdentity":
        for col in FEEDBACK_IDENTITY_BASE_FEATURES:
            if col not in df.columns:
                df[col] = 0.0
    else:
        for col in IDENTITY_ONLY_BASE_FEATURES:
            if col not in df.columns:
                df[col] = 0.0

    model = load_model(model_dir, model_type)
    result = model.predict(df)

    return result
