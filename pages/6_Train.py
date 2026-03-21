"""Train local model from curation data."""

import logging

import numpy as np
import pandas as pd
import streamlit as st

from core.config import load_config
from core.database import (
    get_connection,
    get_all_identities,
    get_articles_for_person,
    get_curations,
)
from core.feature_generator import compute_features
from core.preprocessing import (
    FEEDBACK_IDENTITY_BASE_FEATURES,
    FEEDBACK_IDENTITY_FEATURES,
    compute_derived_features_feedback_identity,
)

st.title("Train Local Model")

conn = get_connection()
config = load_config()
identities = get_all_identities(conn)

if not identities:
    st.warning("No researchers loaded.")
    st.stop()

# ── Gather training data stats ───────────────────────────────────────────────

st.header("Training Data Overview")

total_accepted = 0
total_rejected = 0
persons_with_data = 0

for identity in identities:
    curations = get_curations(conn, identity.person_id)
    acc = sum(1 for v in curations.values() if v == "ACCEPTED")
    rej = sum(1 for v in curations.values() if v == "REJECTED")
    if acc + rej > 0:
        persons_with_data += 1
    total_accepted += acc
    total_rejected += rej

total_curated = total_accepted + total_rejected

col1, col2, col3, col4 = st.columns(4)
col1.metric("Researchers with data", persons_with_data)
col2.metric("Total curated", total_curated)
col3.metric("Accepted", total_accepted)
col4.metric("Rejected", total_rejected)

# Warnings
if total_curated < 100:
    st.warning(
        f"Only {total_curated} curated articles. "
        "We recommend at least 100 for reliable model training."
    )
if total_accepted < 10:
    st.error(
        f"Only {total_accepted} accepted articles. "
        "Need at least 10 accepted articles to train a model."
    )
    st.stop()

st.markdown(
    "Training will treat **PENDING articles as REJECTED** (for training only). "
    "This is consistent with the assumption that uncurated articles are more "
    "likely to be non-matches."
)

# ── Train model ──────────────────────────────────────────────────────────────

if st.button("Train Local Model", type="primary"):
    progress = st.progress(0, text="Collecting training data...")

    all_feature_rows = []
    all_labels = []

    for i, identity in enumerate(identities):
        curations = get_curations(conn, identity.person_id)
        articles = get_articles_for_person(conn, identity.person_id)

        if not articles:
            continue

        # For training: PENDING → REJECTED
        for article in articles:
            if article.user_assertion not in ("ACCEPTED", "REJECTED"):
                article.user_assertion = "REJECTED"

        feature_rows = compute_features(identity, articles, config)

        for row in feature_rows:
            pmid = row["pmid"]
            assertion = curations.get(pmid, "REJECTED")
            row["label"] = 1 if assertion == "ACCEPTED" else 0
            row["personIdentifier"] = identity.person_id
            all_feature_rows.append(row)

        progress.progress(
            (i + 1) / len(identities),
            text=f"Processing {identity.person_id}...",
        )

    if not all_feature_rows:
        st.error("No training data generated.")
        st.stop()

    df = pd.DataFrame(all_feature_rows)
    progress.progress(0.7, text="Computing derived features...")

    # Ensure all base features
    for col in FEEDBACK_IDENTITY_BASE_FEATURES:
        if col not in df.columns:
            df[col] = 0.0
    df[FEEDBACK_IDENTITY_BASE_FEATURES] = df[FEEDBACK_IDENTITY_BASE_FEATURES].fillna(0)

    # Compute derived features
    df = compute_derived_features_feedback_identity(df)

    features = df[FEEDBACK_IDENTITY_FEATURES]
    labels = df["label"]

    st.write(f"Training data: {len(df)} articles, {labels.sum()} accepted, {(1-labels).sum():.0f} rejected")

    progress.progress(0.8, text="Training XGBoost model...")

    # Train-test split
    from sklearn.model_selection import train_test_split
    from sklearn.preprocessing import StandardScaler
    from sklearn.isotonic import IsotonicRegression
    import xgboost as xgb
    import joblib
    from pathlib import Path

    X_train, X_val, y_train, y_val = train_test_split(
        features, labels, test_size=0.2, random_state=42, stratify=labels,
    )

    # Scale
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_val_scaled = scaler.transform(X_val)

    # Train XGBoost
    model = xgb.XGBClassifier(
        n_estimators=300,
        max_depth=6,
        learning_rate=0.1,
        subsample=0.8,
        colsample_bytree=0.8,
        eval_metric="logloss",
        random_state=42,
    )
    model.fit(X_train_scaled, y_train)

    # Calibrate with isotonic regression
    val_probs = model.predict_proba(X_val_scaled)[:, 1]
    calibrator = IsotonicRegression(out_of_bounds="clip")
    calibrator.fit(val_probs, y_val)

    progress.progress(0.95, text="Saving model...")

    # Save
    model_dir = Path(__file__).parent.parent / "models" / "local"
    model_dir.mkdir(parents=True, exist_ok=True)

    joblib.dump(model, model_dir / "feedbackIdentityModel.joblib")
    joblib.dump(scaler, model_dir / "feedbackIdentityScaler.joblib")
    joblib.dump(calibrator, model_dir / "feedbackIdentityCalibrator.joblib")

    progress.progress(1.0, text="Done!")

    # Evaluate
    from sklearn.metrics import accuracy_score, roc_auc_score, precision_recall_fscore_support

    cal_probs = calibrator.predict(val_probs)
    preds = (cal_probs >= 0.5).astype(int)

    accuracy = accuracy_score(y_val, preds)
    auc = roc_auc_score(y_val, cal_probs)
    precision, recall, f1, _ = precision_recall_fscore_support(
        y_val, preds, average="binary"
    )

    st.success("Local model trained and saved.")

    st.subheader("Validation Metrics")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Accuracy", f"{accuracy:.3f}")
    col2.metric("AUC", f"{auc:.3f}")
    col3.metric("Precision", f"{precision:.3f}")
    col4.metric("Recall", f"{recall:.3f}")

conn.close()
