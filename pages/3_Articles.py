"""Article retrieval — fetch articles from PubMed or upload PMIDs."""

import pandas as pd
import streamlit as st

from core.config import load_config
from core.database import (
    get_connection,
    get_all_identities,
    save_articles,
    link_person_articles,
    get_articles_for_person,
)
from core.pubmed import fetch_articles, search_by_name

st.title("Articles")

conn = get_connection()
config = load_config()
api_key = config.get("pubmed", {}).get("api_key", "")
identities = get_all_identities(conn)

if not identities:
    st.warning("No researchers loaded. Go to **Researchers** page first.")
    st.stop()

# ── Mode selection ───────────────────────────────────────────────────────────

mode = st.radio(
    "Retrieval mode",
    ["Upload PMIDs", "Search PubMed by name"],
    horizontal=True,
)

# ── Mode A: Upload PMIDs ─────────────────────────────────────────────────────

if mode == "Upload PMIDs":
    st.markdown(
        "Upload a CSV with columns: `person_id`, `pmid`. "
        "Article metadata will be fetched from PubMed."
    )

    uploaded = st.file_uploader("Choose CSV file", type=["csv"], key="pmid_upload")

    if uploaded is not None:
        try:
            df = pd.read_csv(uploaded)
            required = {"person_id", "pmid"}
            missing = required - set(df.columns)
            if missing:
                st.error(f"Missing required columns: {missing}")
                st.stop()

            st.write(f"Found {len(df)} person-article pairs")
            st.dataframe(df.head(10))

            if st.button("Fetch and Import", type="primary"):
                # Group by person
                grouped = df.groupby("person_id")["pmid"].apply(list).to_dict()

                all_pmids = list(set(df["pmid"].tolist()))
                st.write(f"Fetching {len(all_pmids)} unique articles from PubMed...")

                progress = st.progress(0)
                articles = fetch_articles(all_pmids, api_key=api_key)
                progress.progress(0.8)

                # Save articles
                save_articles(conn, articles)

                # Link to persons
                for person_id, pmids in grouped.items():
                    link_person_articles(conn, str(person_id), pmids)

                progress.progress(1.0)
                st.success(
                    f"Imported {len(articles)} articles for "
                    f"{len(grouped)} researchers."
                )
                st.rerun()
        except Exception as e:
            st.error(f"Error: {e}")

# ── Mode B: Search PubMed ────────────────────────────────────────────────────

else:
    person_options = {
        f"{i.person_id} — {i.first_name} {i.last_name}": i
        for i in identities
    }
    selected_key = st.selectbox("Select researcher", list(person_options.keys()))
    identity = person_options[selected_key]

    col1, col2 = st.columns(2)
    with col1:
        search_first = st.text_input("First name", value=identity.first_name)
    with col2:
        search_last = st.text_input("Last name", value=identity.last_name)

    search_affiliation = st.text_input(
        "Affiliation filter (optional)",
        value=identity.primary_institution,
    )

    if st.button("Search PubMed"):
        with st.spinner("Searching PubMed..."):
            pmids = search_by_name(
                search_first, search_last,
                affiliation=search_affiliation,
                api_key=api_key,
            )

        if not pmids:
            st.warning("No results found.")
        else:
            st.write(f"Found {len(pmids)} articles")
            st.session_state["search_pmids"] = pmids
            st.session_state["search_person_id"] = identity.person_id

    # Show search results and allow import
    if "search_pmids" in st.session_state:
        pmids = st.session_state["search_pmids"]
        person_id = st.session_state["search_person_id"]

        st.write(f"**{len(pmids)} PMIDs** found for {person_id}")

        # Show first few
        st.text(f"First 20 PMIDs: {pmids[:20]}")

        max_import = st.number_input(
            "Max articles to import",
            min_value=1, max_value=len(pmids), value=min(200, len(pmids)),
        )

        if st.button("Fetch and Import Articles", type="primary"):
            selected_pmids = pmids[:max_import]
            with st.spinner(f"Fetching {len(selected_pmids)} articles..."):
                articles = fetch_articles(selected_pmids, api_key=api_key)
                save_articles(conn, articles)
                link_person_articles(conn, person_id, [a.pmid for a in articles])

            st.success(f"Imported {len(articles)} articles for {person_id}.")
            del st.session_state["search_pmids"]
            del st.session_state["search_person_id"]
            st.rerun()

# ── Current articles summary ─────────────────────────────────────────────────

st.header("Current Articles")

for identity in identities:
    articles = get_articles_for_person(conn, identity.person_id)
    if articles:
        with st.expander(
            f"{identity.person_id} — {identity.first_name} {identity.last_name} "
            f"({len(articles)} articles)"
        ):
            rows = []
            for a in articles[:50]:
                rows.append({
                    "PMID": a.pmid,
                    "Year": a.pub_year,
                    "Title": a.title[:80] + ("..." if len(a.title) > 80 else ""),
                    "Journal": a.journal_title[:40],
                    "Authors": a.author_count,
                    "Status": a.user_assertion or "PENDING",
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
            if len(articles) > 50:
                st.caption(f"Showing first 50 of {len(articles)} articles.")

conn.close()
