"""Export results as CSV."""

import io

import pandas as pd
import streamlit as st

from core.database import (
    get_connection,
    get_all_identities,
    get_articles_for_person,
    get_curations,
    get_person_stats,
)

st.title("Export")

conn = get_connection()
identities = get_all_identities(conn)

if not identities:
    st.warning("No researchers loaded.")
    st.stop()

# ── Export options ────────────────────────────────────────────────────────────

export_type = st.radio(
    "Export type",
    ["Full Results (with scores)", "Summary by Researcher", "Curations (for re-import)"],
    horizontal=True,
)

# ── Full results ─────────────────────────────────────────────────────────────

if export_type == "Full Results (with scores)":
    st.markdown("Export all articles with scores, features, and curation status.")

    person_options = ["All Researchers"] + [
        f"{i.person_id} — {i.first_name} {i.last_name}" for i in identities
    ]
    selected = st.selectbox("Researcher", person_options)

    if st.button("Generate Export", type="primary"):
        rows = []
        target_identities = identities if selected == "All Researchers" else [
            i for i in identities if f"{i.person_id} — {i.first_name} {i.last_name}" == selected
        ]

        for identity in target_identities:
            articles = get_articles_for_person(conn, identity.person_id)
            curations = get_curations(conn, identity.person_id)

            # Try to get cached scores
            score_key = f"scores_{identity.person_id}"
            score_lookup = {}
            if score_key in st.session_state:
                score_df = st.session_state[score_key]
                for _, srow in score_df.iterrows():
                    score_lookup[int(srow["pmid"])] = {
                        "raw_score": srow.get("raw_score", ""),
                        "calibrated_score": srow.get("calibrated_score", ""),
                    }

            for article in articles:
                score_data = score_lookup.get(article.pmid, {})
                target = article.target_author

                rows.append({
                    "person_id": identity.person_id,
                    "first_name": identity.first_name,
                    "last_name": identity.last_name,
                    "pmid": article.pmid,
                    "title": article.title,
                    "journal": article.journal_title,
                    "year": article.pub_year,
                    "doi": article.doi,
                    "authors": article.author_count,
                    "target_author": target.full_name if target else "",
                    "target_author_rank": target.rank if target else 0,
                    "calibrated_score": score_data.get("calibrated_score", ""),
                    "raw_score": score_data.get("raw_score", ""),
                    "status": curations.get(article.pmid, "PENDING"),
                })

        if rows:
            df = pd.DataFrame(rows)
            st.dataframe(df, use_container_width=True, hide_index=True)

            csv = df.to_csv(index=False)
            st.download_button(
                "Download CSV",
                csv,
                file_name="reciter_desktop_results.csv",
                mime="text/csv",
            )
        else:
            st.info("No data to export.")

# ── Summary ──────────────────────────────────────────────────────────────────

elif export_type == "Summary by Researcher":
    rows = []
    for identity in identities:
        stats = get_person_stats(conn, identity.person_id)
        rows.append({
            "person_id": identity.person_id,
            "first_name": identity.first_name,
            "last_name": identity.last_name,
            "department": identity.department,
            "total_articles": stats["total_articles"],
            "accepted": stats["accepted"],
            "rejected": stats["rejected"],
            "pending": stats["pending"],
            "acceptance_rate": round(stats["acceptance_rate"], 3),
        })

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)

    csv = df.to_csv(index=False)
    st.download_button(
        "Download CSV",
        csv,
        file_name="reciter_desktop_summary.csv",
        mime="text/csv",
    )

# ── Curations for re-import ──────────────────────────────────────────────────

else:
    st.markdown(
        "Export curations as CSV for backup or to continue curation later. "
        "This file can be re-uploaded in the Articles page."
    )

    rows = []
    for identity in identities:
        curations = get_curations(conn, identity.person_id)
        for pmid, assertion in curations.items():
            rows.append({
                "person_id": identity.person_id,
                "pmid": pmid,
                "assertion": assertion,
            })

    if rows:
        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.write(f"**{len(rows)}** curations")

        csv = df.to_csv(index=False)
        st.download_button(
            "Download CSV",
            csv,
            file_name="reciter_desktop_curations.csv",
            mime="text/csv",
        )
    else:
        st.info("No curations to export.")

conn.close()
