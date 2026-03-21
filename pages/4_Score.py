"""Scoring dashboard — run the scoring pipeline and view results."""

import pandas as pd
import numpy as np
import streamlit as st

from core.config import load_config
from core.database import (
    get_connection,
    get_all_identities,
    get_articles_for_person,
    get_curations,
    save_scores,
    get_cached_scores,
)
from core.feature_generator import compute_features
from core.scoring import score_articles

st.title("Score")

conn = get_connection()
config = load_config()
identities = get_all_identities(conn)

if not identities:
    st.warning("No researchers loaded. Go to **Researchers** page first.")
    st.stop()

# ── Controls ─────────────────────────────────────────────────────────────────

col1, col2 = st.columns(2)

with col1:
    person_options = {
        f"{i.person_id} — {i.first_name} {i.last_name}": i for i in identities
    }
    selected_key = st.selectbox("Researcher", list(person_options.keys()))
    identity = person_options[selected_key]

with col2:
    # Check if local model exists
    from pathlib import Path
    local_model_exists = (Path(__file__).parent.parent / "models" / "local" / "feedbackIdentityModel.joblib").exists()

    model_options = ["WCM Model"]
    if local_model_exists:
        model_options.append("Local Model")
        model_options.append("Compare Both")

    model_choice = st.selectbox("Model", model_options)

# ── Run scoring ──────────────────────────────────────────────────────────────

articles = get_articles_for_person(conn, identity.person_id)
if not articles:
    st.info(f"No articles found for {identity.person_id}. Go to **Articles** page first.")
    st.stop()

curations = get_curations(conn, identity.person_id)
has_feedback = bool(curations)

# Determine model type
if has_feedback:
    model_type = "feedbackIdentity"
else:
    model_type = "identityOnly"
    if model_choice != "WCM Model":
        st.info("No curated articles — using Identity-Only model (WCM).")
        model_choice = "WCM Model"

st.write(
    f"**{len(articles)}** articles | "
    f"**{sum(1 for v in curations.values() if v == 'ACCEPTED')}** accepted, "
    f"**{sum(1 for v in curations.values() if v == 'REJECTED')}** rejected | "
    f"Model: **{model_type}**"
)

if st.button("Run Scoring", type="primary"):
    with st.spinner("Computing features and scoring..."):
        # Compute features
        feature_rows = compute_features(identity, articles, config)

        # Score
        model_dir = "wcm" if model_choice in ("WCM Model", "Compare Both") else "local"
        result_df = score_articles(
            feature_rows, curations,
            model_dir=model_dir,
            identity_first_name=identity.first_name,
        )

        # Save to cache
        score_data = result_df[["pmid", "raw_score", "calibrated_score"]].to_dict("records")
        save_scores(conn, identity.person_id, model_type, model_dir, score_data)

        st.session_state[f"scores_{identity.person_id}"] = result_df

        # If comparing, also score with local model
        if model_choice == "Compare Both":
            result_local = score_articles(
                feature_rows, curations,
                model_dir="local",
                identity_first_name=identity.first_name,
            )
            st.session_state[f"scores_local_{identity.person_id}"] = result_local

    st.success("Scoring complete.")

# ── Display results ──────────────────────────────────────────────────────────

score_key = f"scores_{identity.person_id}"
if score_key not in st.session_state:
    st.info("Click **Run Scoring** to generate scores.")
    st.stop()

result_df = st.session_state[score_key]

# Build display table
article_lookup = {a.pmid: a for a in articles}
display_rows = []
for _, row in result_df.iterrows():
    pmid = int(row["pmid"])
    art = article_lookup.get(pmid)
    score = row["calibrated_score"]
    display_rows.append({
        "PMID": pmid,
        "Score": round(score, 3),
        "Status": curations.get(pmid, "PENDING"),
        "Year": art.pub_year if art else 0,
        "Title": (art.title[:70] + "...") if art and len(art.title) > 70 else (art.title if art else ""),
        "Journal": (art.journal_title[:35]) if art else "",
        "Authors": art.author_count if art else 0,
    })

display_df = pd.DataFrame(display_rows).sort_values("Score", ascending=False)

# Color code by score
def color_score(val):
    if val >= 0.7:
        return "background-color: #c6efce"  # green
    elif val >= 0.3:
        return "background-color: #ffeb9c"  # yellow
    else:
        return "background-color: #ffc7ce"  # red

st.dataframe(
    display_df.style.applymap(color_score, subset=["Score"]),
    use_container_width=True,
    hide_index=True,
    height=500,
)

# Score distribution
st.subheader("Score Distribution")
col1, col2 = st.columns(2)
with col1:
    st.bar_chart(
        pd.cut(display_df["Score"], bins=10).value_counts().sort_index(),
    )
with col2:
    st.metric("Mean Score", f"{display_df['Score'].mean():.3f}")
    st.metric("Median Score", f"{display_df['Score'].median():.3f}")
    st.metric("> 0.5", f"{(display_df['Score'] > 0.5).sum()}")
    st.metric("< 0.3", f"{(display_df['Score'] < 0.3).sum()}")

# Compare models side by side
local_key = f"scores_local_{identity.person_id}"
if local_key in st.session_state:
    st.subheader("Model Comparison: WCM vs Local")
    local_df = st.session_state[local_key]
    merged = result_df[["pmid", "calibrated_score"]].merge(
        local_df[["pmid", "calibrated_score"]],
        on="pmid", suffixes=("_wcm", "_local"),
    )
    st.scatter_chart(
        merged.set_index("pmid")[["calibrated_score_wcm", "calibrated_score_local"]],
    )

conn.close()
