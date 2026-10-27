"""OMOP Mapping Review — navigation router."""
import streamlit as st

st.set_page_config(page_title="OMOP Mapping Review", layout="wide")

pg = st.navigation([
    st.Page("views/home.py", title="Overview", default=True),
    st.Page("views/worklist.py", title="Worklist"),
    st.Page("views/approver.py", title="Approve"),
    st.Page("views/reference.py", title="Reference"),
    st.Page("views/schema.py", title="How it works"),
])
pg.run()
