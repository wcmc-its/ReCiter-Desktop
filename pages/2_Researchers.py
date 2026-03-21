"""Researcher management — upload/manage researcher identities."""

import io

import pandas as pd
import streamlit as st

from core.database import (
    get_connection,
    save_identities,
    get_all_identities,
    get_person_stats,
    delete_identity,
)
from core.identity import Identity

st.title("Researchers")

conn = get_connection()

# ── Upload CSV ───────────────────────────────────────────────────────────────

st.header("Upload Researcher Identities")
st.markdown(
    "Upload a CSV with columns: `person_id`, `first_name`, `last_name` (required), "
    "and optionally: `middle_name`, `email`, `institution`, `department`, `title`, "
    "`orcid`, `bachelor_year`, `doctoral_year`."
)

uploaded = st.file_uploader("Choose CSV file", type=["csv"])

if uploaded is not None:
    try:
        df = pd.read_csv(uploaded)
        st.write(f"Found {len(df)} rows")

        required = {"person_id", "first_name", "last_name"}
        missing = required - set(df.columns)
        if missing:
            st.error(f"Missing required columns: {missing}")
        else:
            st.dataframe(df.head(10))
            if st.button("Import Researchers", type="primary"):
                identities = []
                for _, row in df.iterrows():
                    identities.append(Identity.from_dict(row.to_dict()))
                save_identities(conn, identities)
                st.success(f"Imported {len(identities)} researchers.")
                st.rerun()
    except Exception as e:
        st.error(f"Error reading CSV: {e}")

# ── Existing researchers ─────────────────────────────────────────────────────

st.header("Researchers")

identities = get_all_identities(conn)

if not identities:
    st.info("No researchers loaded yet. Upload a CSV above.")
else:
    # Build stats table
    rows = []
    for ident in identities:
        stats = get_person_stats(conn, ident.person_id)
        rows.append({
            "Person ID": ident.person_id,
            "Name": f"{ident.first_name} {ident.middle_name} {ident.last_name}".strip(),
            "Email": ident.primary_email,
            "Department": ident.department,
            "Articles": stats["total_articles"],
            "Accepted": stats["accepted"],
            "Rejected": stats["rejected"],
            "Pending": stats["pending"],
        })

    st.dataframe(
        pd.DataFrame(rows),
        use_container_width=True,
        hide_index=True,
    )

    # Delete researcher
    with st.expander("Delete a researcher"):
        person_ids = [i.person_id for i in identities]
        to_delete = st.selectbox("Select researcher to delete", person_ids)
        if st.button("Delete", type="secondary"):
            delete_identity(conn, to_delete)
            st.success(f"Deleted {to_delete}")
            st.rerun()

conn.close()
