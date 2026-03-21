"""Curation interface — accept/reject articles."""

import pandas as pd
import streamlit as st

from core.database import (
    get_connection,
    get_all_identities,
    get_articles_for_person,
    get_curations,
    save_curation,
    save_curations_batch,
)

st.title("Curate")

conn = get_connection()
identities = get_all_identities(conn)

if not identities:
    st.warning("No researchers loaded.")
    st.stop()

# ── Select researcher ────────────────────────────────────────────────────────

person_options = {
    f"{i.person_id} — {i.first_name} {i.last_name}": i for i in identities
}
selected_key = st.selectbox("Researcher", list(person_options.keys()))
identity = person_options[selected_key]

articles = get_articles_for_person(conn, identity.person_id)
if not articles:
    st.info("No articles for this researcher.")
    st.stop()

curations = get_curations(conn, identity.person_id)

# ── Summary ──────────────────────────────────────────────────────────────────

accepted = sum(1 for v in curations.values() if v == "ACCEPTED")
rejected = sum(1 for v in curations.values() if v == "REJECTED")
pending = len(articles) - accepted - rejected

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total", len(articles))
col2.metric("Accepted", accepted)
col3.metric("Rejected", rejected)
col4.metric("Pending", pending)

# ── Sort options ─────────────────────────────────────────────────────────────

sort_option = st.radio(
    "Sort by",
    ["Score (highest first)", "Score (lowest first)", "Year (newest)", "Pending first"],
    horizontal=True,
)

# Check if we have cached scores
score_key = f"scores_{identity.person_id}"
has_scores = score_key in st.session_state

score_lookup = {}
if has_scores:
    score_df = st.session_state[score_key]
    score_lookup = dict(zip(score_df["pmid"].astype(int), score_df["calibrated_score"]))

# Sort articles
if sort_option == "Score (highest first)" and score_lookup:
    articles.sort(key=lambda a: score_lookup.get(a.pmid, 0.5), reverse=True)
elif sort_option == "Score (lowest first)" and score_lookup:
    articles.sort(key=lambda a: score_lookup.get(a.pmid, 0.5))
elif sort_option == "Year (newest)":
    articles.sort(key=lambda a: a.pub_year, reverse=True)
elif sort_option == "Pending first":
    articles.sort(key=lambda a: (0 if a.user_assertion == "" else 1, -a.pub_year))

# ── Bulk actions ─────────────────────────────────────────────────────────────

if score_lookup:
    st.subheader("Bulk Actions")
    threshold = st.slider("Score threshold", 0.0, 1.0, 0.7, 0.05)

    col1, col2 = st.columns(2)
    with col1:
        above = [a for a in articles if score_lookup.get(a.pmid, 0) >= threshold
                 and curations.get(a.pmid, "") == ""]
        if st.button(f"Accept all {len(above)} above {threshold}", disabled=len(above) == 0):
            batch = {a.pmid: "ACCEPTED" for a in above}
            save_curations_batch(conn, identity.person_id, batch)
            st.success(f"Accepted {len(batch)} articles.")
            st.rerun()

    with col2:
        below_thresh = 1.0 - threshold
        below = [a for a in articles if score_lookup.get(a.pmid, 1) < below_thresh
                 and curations.get(a.pmid, "") == ""]
        if st.button(f"Reject all {len(below)} below {below_thresh:.2f}", disabled=len(below) == 0):
            batch = {a.pmid: "REJECTED" for a in below}
            save_curations_batch(conn, identity.person_id, batch)
            st.success(f"Rejected {len(batch)} articles.")
            st.rerun()

# ── Filter ───────────────────────────────────────────────────────────────────

filter_status = st.multiselect(
    "Show",
    ["PENDING", "ACCEPTED", "REJECTED"],
    default=["PENDING"],
)

filtered = []
for a in articles:
    status = curations.get(a.pmid, "PENDING")
    if not status:
        status = "PENDING"
    if status in filter_status:
        filtered.append(a)

st.write(f"Showing {len(filtered)} articles")

# ── Article cards ────────────────────────────────────────────────────────────

for article in filtered[:100]:
    status = curations.get(article.pmid, "")
    score = score_lookup.get(article.pmid)
    score_str = f" | Score: **{score:.3f}**" if score is not None else ""

    # Status badge
    if status == "ACCEPTED":
        badge = ":green[ACCEPTED]"
    elif status == "REJECTED":
        badge = ":red[REJECTED]"
    else:
        badge = ":orange[PENDING]"

    with st.container(border=True):
        st.markdown(
            f"**PMID {article.pmid}** | {article.pub_year} | "
            f"{article.journal_title}{score_str} | {badge}"
        )
        st.markdown(f"**{article.title}**")

        # Authors with target author highlighted
        author_strs = []
        for i, author in enumerate(article.authors):
            name = f"{author.first_name} {author.last_name}".strip()
            if i == article.target_author_index:
                author_strs.append(f"**{name}**")
            else:
                author_strs.append(name)
        if author_strs:
            st.markdown(", ".join(author_strs[:15]))
            if len(article.authors) > 15:
                st.caption(f"... and {len(article.authors) - 15} more authors")

        if article.abstract:
            with st.expander("Abstract"):
                st.write(article.abstract)

        # Accept / Reject buttons
        col1, col2, col3 = st.columns([1, 1, 4])
        with col1:
            if st.button(
                "Accept" if status != "ACCEPTED" else "Undo Accept",
                key=f"accept_{article.pmid}",
                type="primary" if status != "ACCEPTED" else "secondary",
            ):
                new_status = "" if status == "ACCEPTED" else "ACCEPTED"
                if new_status:
                    save_curation(conn, identity.person_id, article.pmid, new_status)
                else:
                    conn.execute(
                        "DELETE FROM curations WHERE person_id = ? AND pmid = ?",
                        (identity.person_id, article.pmid),
                    )
                    conn.commit()
                st.rerun()
        with col2:
            if st.button(
                "Reject" if status != "REJECTED" else "Undo Reject",
                key=f"reject_{article.pmid}",
                type="secondary",
            ):
                new_status = "" if status == "REJECTED" else "REJECTED"
                if new_status:
                    save_curation(conn, identity.person_id, article.pmid, new_status)
                else:
                    conn.execute(
                        "DELETE FROM curations WHERE person_id = ? AND pmid = ?",
                        (identity.person_id, article.pmid),
                    )
                    conn.commit()
                st.rerun()

if len(filtered) > 100:
    st.caption(f"Showing first 100 of {len(filtered)} articles.")

conn.close()
