"""Setup wizard — configure institution settings and PubMed API key."""

import streamlit as st
from core.config import load_config, save_user_config, is_configured

st.title("Setup")

if is_configured():
    st.success("Setup complete. You can update settings below.")

config = load_config()
inst = config.get("institution", {})
pubmed = config.get("pubmed", {})

st.header("PubMed API Key")
st.markdown(
    "An API key increases PubMed rate limits from 3 to 10 requests/second. "
    "[Request one here](https://www.ncbi.nlm.nih.gov/account/settings/)."
)
api_key = st.text_input(
    "API Key (optional but recommended)",
    value=pubmed.get("api_key", ""),
    type="password",
)

st.header("Institution Settings")

label = st.text_input(
    "Institution Name",
    value=inst.get("institution_label", ""),
    placeholder="e.g., Weill Cornell Medicine",
)

email_suffixes_str = st.text_input(
    "Email Domains (comma-separated)",
    value=", ".join(inst.get("email_suffixes", [])),
    placeholder="e.g., @med.cornell.edu, @nyp.org",
)

st.markdown(
    "**Home Institution Keywords** — Groups of keywords that identify your institution "
    "in PubMed affiliation strings. Each line is a group; use `|` to separate keywords "
    "within a group. All keywords in a group must appear for a match."
)
default_kw = "\n".join(
    "|".join(g) if isinstance(g, list) else g
    for g in inst.get("home_institution_keywords", [])
)
home_keywords_str = st.text_area(
    "Keyword Groups (one per line, pipe-separated)",
    value=default_kw,
    placeholder="e.g.,\nweill|cornell\ncornell|medicine\n10065|cornell",
    height=150,
)

st.header("Departments (Optional)")
st.markdown(
    "List your departments to enable organizational unit matching and journal subfield evidence."
)
departments_str = st.text_area(
    "Departments (one per line)",
    value="",
    placeholder="e.g.,\nMedicine\nPediatrics\nSurgery",
    height=100,
)

st.header("Collaborating Institution Keywords (Optional)")
collab_kw_str = st.text_area(
    "Collaborating institutions (one group per line, pipe-separated)",
    value="\n".join(
        "|".join(g) if isinstance(g, list) else g
        for g in inst.get("collaborating_keywords", [])
    ),
    placeholder="e.g.,\nmemorial|sloan|kettering\nrockefeller|university",
    height=100,
)

if st.button("Save Configuration", type="primary"):
    email_suffixes = [
        s.strip() for s in email_suffixes_str.split(",") if s.strip()
    ]

    home_keywords = []
    for line in home_keywords_str.strip().split("\n"):
        line = line.strip()
        if line:
            home_keywords.append(line)

    collab_keywords = []
    for line in collab_kw_str.strip().split("\n"):
        line = line.strip()
        if line:
            collab_keywords.append(line)

    updates = {
        "pubmed": {"api_key": api_key},
        "institution": {
            "institution_label": label,
            "email_suffixes": email_suffixes,
            "home_institution_keywords": home_keywords,
            "collaborating_keywords": collab_keywords,
        },
    }

    save_user_config(updates)
    st.success("Configuration saved.")
    st.rerun()
