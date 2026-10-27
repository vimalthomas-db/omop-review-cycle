"""OMOP Mapping Review — Reference Explorer (read-only search of the 3 CDM tables)."""
import streamlit as st
from lib import uc, style

style.inject()
style.header("Reference",
             "Look up the OMOP vocabulary: concepts (the dictionary), how they map to one another, "
             "and the local code mappings. Read-only.",
             eyebrow="Vocabulary")

term = st.text_input("Search by code or name", placeholder="e.g. hemorrhage, E11.9, glucose, 192671")

tabs = st.tabs(["concept", "concept_relationship", "source_to_concept_map"])

with tabs[0]:
    st.caption("The dictionary — every concept (Standard 'S' and non-standard). This is where targets come from.")
    try:
        df = uc.ref_concept(term)
        st.caption(f"{len(df)} rows")
        st.dataframe(df, use_container_width=True, hide_index=True)
    except Exception as e:
        st.error(str(e))

with tabs[1]:
    st.caption("The 'Maps to' arrows — links a source/non-standard concept to its Standard concept.")
    try:
        df = uc.ref_relationship(term)
        st.caption(f"{len(df)} rows")
        st.dataframe(df, use_container_width=True, hide_index=True)
    except Exception as e:
        st.error(str(e))

with tabs[2]:
    st.caption("Local-code mappings maintained by the ETL/review process (source_code → target_concept_id).")
    try:
        df = uc.ref_s2cm(term)
        st.caption(f"{len(df)} rows")
        st.dataframe(df, use_container_width=True, hide_index=True)
    except Exception as e:
        st.error(str(e))
