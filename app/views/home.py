"""OMOP Mapping Review — Home."""
import streamlit as st
import plotly.graph_objects as go
from lib import uc, lb, style

style.inject()
style.header(
    "OMOP Mapping Review",
    "Find the source codes that didn't map to a standard concept, decide what each one means, "
    "and write the approved mappings back to the CDM.",
    eyebrow="Overview")


@st.cache_data(ttl=60)
def _cov():
    return uc.get_coverage()


@st.cache_data(ttl=60)
def _wl():
    return uc.get_worklist()


try:
    cov, wl = _cov(), _wl()
except Exception as e:
    st.error(f"Could not load data from Unity Catalog: {e}")
    st.stop()
try:
    status_map = lb.code_status_map()
except Exception:
    status_map = {}

tot = int(cov["total_records"].sum())
std = int(cov["mapped_standard"].sum())
nonstd = int(cov["mapped_nonstandard"].sum())
overall_pct = round(100 * std / tot, 1) if tot else 0

# ---------- lifecycle tracker ----------
statuses = [v.get("status") for v in status_map.values()]
detected = len(wl)
in_review = sum(1 for s in statuses if s in ("in_review", "reviewed"))
approved = sum(1 for s in statuses if s == "approved")
committed = sum(1 for s in statuses if s == "committed")
style.section("Where things stand")
style.lifecycle([
    ("Detect", detected, "unmapped codes found", style.TEAL),
    ("Review", in_review, "researchers proposing targets", style.AMBER),
    ("Approve", approved, "governance signed off", style.GREEN),
    ("Commit", committed, "written back to the CDM", style.NAVY),
])

# ---------- KPIs ----------
st.write("")
c1, c2, c3, c4 = st.columns(4)
style.kpi(c1, "Standard-mapped", f"{overall_pct}%", f"{std:,} of {tot:,} records")
style.kpi(c2, "Codes to review", f"{detected}", "distinct unmapped source codes")
style.kpi(c3, "Records unmapped", f"{int(wl['record_count'].sum()):,}", "across all domains")
style.kpi(c4, "Non-standard mappings", f"{nonstd:,}", "mapped to a wrong (non-standard) concept")

style.section("Mapping coverage")
left, right = st.columns(2)

# ---------- Chart 1: completeness by domain (one axis: % standard) ----------
with left:
    st.markdown("**Completeness by domain**")
    d = cov.sort_values("pct_standard_mapped")
    fig = go.Figure()
    fig.add_bar(y=d["omop_domain"], x=d["pct_standard_mapped"], orientation="h",
                marker_color=style.GREEN, name="Mapped to standard",
                hovertemplate="%{x:.1f}% mapped<extra></extra>")
    fig.add_bar(y=d["omop_domain"], x=(100 - d["pct_standard_mapped"]), orientation="h",
                marker_color="#E9EDF3", name="Not standard-mapped",
                hovertemplate="%{x:.1f}% gap<extra></extra>")
    fig.update_layout(barmode="stack", height=300, margin=dict(l=0, r=0, t=4, b=0),
                      legend=dict(orientation="h", y=-0.18), plot_bgcolor="white",
                      font=dict(color=style.NAVY))
    fig.update_xaxes(range=[0, 100], ticksuffix="%", gridcolor="#EEF1F6")
    st.plotly_chart(fig, use_container_width=True)

# ---------- Chart 2: of what's unmapped, why (one axis: reason) ----------
with right:
    st.markdown("**Unmapped records, by reason**")
    d = cov.sort_values("unmapped_vocab_gap", ascending=True)
    fig2 = go.Figure()
    fig2.add_bar(y=d["omop_domain"], x=d["unmapped_vocab_gap"], orientation="h",
                 marker_color=style.CORAL, name="Vocab gap (public code, no standard map)")
    fig2.add_bar(y=d["omop_domain"], x=d["unmapped_s2cm_gap"], orientation="h",
                 marker_color=style.RED, name="Local (no map)")
    fig2.update_layout(barmode="stack", height=300, margin=dict(l=0, r=0, t=4, b=0),
                       legend=dict(orientation="h", y=-0.22), plot_bgcolor="white",
                       font=dict(color=style.NAVY))
    fig2.update_xaxes(gridcolor="#EEF1F6", title="records")
    st.plotly_chart(fig2, use_container_width=True)

st.write("")
st.page_link("views/worklist.py", label="Open the review worklist  →")
