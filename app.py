"""
ReCiter Desktop — Streamlit entry point.

Lightweight CARE scoring pipeline for author disambiguation.
"""

import streamlit as st

st.set_page_config(
    page_title="ReCiter Desktop",
    page_icon=":microscope:",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("ReCiter Desktop")
st.markdown("""
**CARE Scoring Pipeline for Author Disambiguation**

ReCiter Desktop is a standalone tool that helps institutions identify which
publications belong to their researchers. It uses the CARE (Comprehensive
Author Recognition Engine) scoring model trained on data from Weill Cornell Medicine.

### Getting Started

Use the sidebar to navigate between pages:

1. **Setup** — Configure your institution settings and PubMed API key
2. **Researchers** — Upload and manage researcher identities
3. **Articles** — Retrieve candidate articles from PubMed
4. **Score** — Run the scoring pipeline to rank articles
5. **Curate** — Accept or reject articles to improve future scoring
6. **Train** — Train a local model from your curation data
7. **Export** — Download results as CSV
""")

# Check configuration status
from core.config import is_configured

if not is_configured():
    st.warning(
        "You haven't completed setup yet. "
        "Go to the **Setup** page to configure your institution."
    )
else:
    from core.config import load_config
    config = load_config()
    inst = config.get("institution", {})
    st.success(f"Configured for: **{inst.get('institution_label', 'Unknown')}**")

    # Show summary stats
    from core.database import get_connection, get_all_identities, get_person_stats
    try:
        conn = get_connection()
        identities = get_all_identities(conn)
        if identities:
            total_articles = 0
            total_curated = 0
            for ident in identities:
                stats = get_person_stats(conn, ident.person_id)
                total_articles += stats["total_articles"]
                total_curated += stats["accepted"] + stats["rejected"]

            col1, col2, col3 = st.columns(3)
            col1.metric("Researchers", len(identities))
            col2.metric("Total Articles", total_articles)
            col3.metric("Curated", total_curated)
        conn.close()
    except Exception:
        pass
