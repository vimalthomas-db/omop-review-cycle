"""OMOP Mapping Review — Worklist (reviewer)."""
import streamlit as st
from lib import uc, lb, config, style

style.inject()
style.header("Worklist",
             "Each row is a source code that didn't map. Decide it once, and the fix applies to every record that uses it.",
             eyebrow="Review")

DECISIONS = ["REMAP", "UNMAPPABLE", "NEW_LOCAL_CONCEPT", "NEEDS_INFO"]
OMOP_DOMAINS = ["Condition", "Drug", "Procedure", "Measurement", "Observation",
                "Device", "Visit", "Specimen", "Note", "Meas Value"]
UNMAPPABLE_REASONS = ["no_standard_exists", "out_of_scope", "junk_code", "ambiguous", "other"]

with st.sidebar:
    st.header("Reviewer")
    reviewer_email = st.text_input("Your email", value=config.current_user_email())
    st.divider()
    st.header("Filters")


@st.cache_data(ttl=60)
def _wl():
    return uc.get_worklist()


try:
    wl = _wl()
except Exception as e:
    st.error(f"Could not load worklist: {e}")
    st.stop()
try:
    status_map = lb.code_status_map()
except Exception as e:
    st.warning(f"Lakebase unavailable: {e}")
    status_map = {}

domains = sorted(wl["omop_domain"].unique())
gaps = sorted(wl["gap_type"].unique())
sel_d = st.sidebar.multiselect("Domain", domains, default=domains)
sel_g = st.sidebar.multiselect("Gap type", gaps, default=gaps)
hide_done = st.sidebar.checkbox("Hide approved / committed", value=True)

view = wl[wl["omop_domain"].isin(sel_d) & wl["gap_type"].isin(sel_g)].copy()
view["status"] = view.apply(
    lambda r: status_map.get(f"{r['domain_table']}:{r['source_value']}", {}).get("status", "open"), axis=1)
if hide_done:
    view = view[~view["status"].isin(["approved", "committed"])]

c1, c2, c3 = st.columns(3)
style.kpi(c1, "Codes shown", f"{len(view)}", "after filters")
style.kpi(c2, "Records affected", f"{int(view['record_count'].sum()):,}", "")
style.kpi(c3, "Reviewed / approved", f"{(view['status'] != 'open').sum()}", "have ≥1 review")
st.write("")


@st.dialog("Add mapping review", width="large")
def review_dialog(row):
    st.markdown(f"### `{row['source_value']}` &nbsp; {style.gap_badge(row['gap_type'])}",
                unsafe_allow_html=True)
    st.caption(f"{row['omop_domain']} · {row['source_code_description'] or '—'} · "
               f"{int(row['record_count']):,} records · source_concept_id {row['source_concept_id']}")
    decision = st.selectbox("Decision", DECISIONS)
    target_id, target_name = None, None
    local_concept, unmappable_reason, needs_info_note = None, None, None
    incomplete = False

    if decision == "REMAP":
        st.caption("Map this source code to an existing Standard concept.")
        term = st.text_input("Search standard concept (name or code)")
        if term:
            hits = uc.search_concepts(row["omop_domain"], term)
            if len(hits):
                opts = {f"{r.concept_id} · {r.concept_name} ({r.vocabulary_id})": r
                        for r in hits.itertuples()}
                ch = opts[st.selectbox("Target — Standard concepts only", list(opts))]
                target_id, target_name = int(ch.concept_id), ch.concept_name
                st.success(f"Target: **{target_id} · {target_name}**")
            else:
                st.warning("No standard concepts match.")
        incomplete = target_id is None

    elif decision == "NEW_LOCAL_CONCEPT":
        st.caption("No Standard concept fits — propose a new local concept "
                   "(a 2-billion concept_id is minted at commit).")
        dom_default = row["omop_domain"] if row["omop_domain"] in OMOP_DOMAINS else OMOP_DOMAINS[0]
        name = st.text_input("Concept name *")
        cc1, cc2 = st.columns(2)
        domain_id = cc1.selectbox("Domain", OMOP_DOMAINS, index=OMOP_DOMAINS.index(dom_default))
        vocabulary_id = cc2.text_input("Vocabulary", value="OMOP Extension")
        cc3, cc4 = st.columns(2)
        concept_class_id = cc3.text_input("Concept class")
        concept_code = cc4.text_input("Concept code", value=str(row["source_value"]))
        local_concept = {"name": name or None, "domain_id": domain_id,
                         "vocabulary_id": vocabulary_id or None,
                         "concept_class_id": concept_class_id or None,
                         "concept_code": concept_code or None}
        incomplete = not name

    elif decision == "UNMAPPABLE":
        st.caption("This source code cannot map to any standard concept.")
        unmappable_reason = st.selectbox("Reason", UNMAPPABLE_REASONS)
        incomplete = not unmappable_reason

    elif decision == "NEEDS_INFO":
        st.caption("Park this code — capture what's needed to decide.")
        needs_info_note = st.text_area("What's needed / who to ask *")
        incomplete = not (needs_info_note and needs_info_note.strip())

    conf = st.select_slider("Confidence", ["low", "medium", "high"], value="medium")
    rationale = st.text_area("Rationale / clinical justification")
    if st.button("Submit review", type="primary", disabled=incomplete, use_container_width=True):
        try:
            lb.submit_review(row.to_dict(), decision, target_id, target_name, conf, rationale,
                             reviewer_email, local_concept=local_concept,
                             unmappable_reason=unmappable_reason, needs_info_note=needs_info_note)
            st.cache_data.clear()
            st.toast("Review submitted")
            st.rerun()
        except Exception as e:
            st.error(f"Submit failed: {e}")


@st.dialog("Reviews for this code", width="large")
def reviews_dialog(row):
    code_key = f"{row['domain_table']}:{row['source_value']}"
    st.markdown(f"### `{row['source_value']}` · {row['omop_domain']}")
    try:
        revs = lb.get_reviews(code_key)
    except Exception as e:
        st.error(f"Could not load reviews: {e}")
        return
    if not revs:
        st.info("No reviews yet for this code.")
        return
    for r in revs:
        if r["decision"] == "REMAP" and r["proposed_target_concept_id"]:
            detail = f" → <b>{r['proposed_target_concept_id']}</b> ({r['proposed_target_name']})"
        elif r["decision"] == "NEW_LOCAL_CONCEPT":
            detail = (f" → new local: <b>{r['proposed_concept_name'] or '—'}</b> "
                      f"[{r['proposed_domain_id'] or '—'} · {r['proposed_vocabulary_id'] or '—'} · "
                      f"{r['proposed_concept_class_id'] or '—'} · code {r['proposed_concept_code'] or '—'}]")
        elif r["decision"] == "UNMAPPABLE":
            detail = f" · reason: <b>{r['unmappable_reason'] or '—'}</b>"
        elif r["decision"] == "NEEDS_INFO":
            detail = f" · needs: {r['needs_info_note'] or '—'}"
        else:
            detail = ""
        st.markdown(
            f"<div class='card'><b>{r['decision']}</b>{detail} "
            f"<span class='chip' style='color:{style.TEAL};border-color:{style.TEAL}'>{r['confidence']}</span>"
            f"<br><span class='meta'>{r['reviewer_email']} · {r['created_at']:%Y-%m-%d %H:%M}</span>"
            f"<br>{r['rationale'] or ''}</div>", unsafe_allow_html=True)


for _, row in view.iterrows():
    code_key = f"{row['domain_table']}:{row['source_value']}"
    info = status_map.get(code_key, {})
    with st.container(border=True):
        a, b, c, d = st.columns([2.1, 1.5, 2.6, 1.7])
        a.markdown(f'<span class="code">{row["source_value"]}</span><br>'
                   f'<span class="meta">{row["omop_domain"]}</span>', unsafe_allow_html=True)
        b.markdown(f'{style.gap_badge(row["gap_type"])}<br>{style.status_chip(info.get("status","open"))}',
                   unsafe_allow_html=True)
        c.markdown(f'<span class="meta">{row["source_code_description"] or "—"}</span>'
                   f'<br><span class="meta">{row["record_count_display"]} recs · '
                   f'{row["pct_of_unmapped_domain"]}% of domain</span>'
                   f'{style.priority_bar(row["pct_of_unmapped_domain"])}', unsafe_allow_html=True)
        with d:
            locked = bool(info.get("locked"))
            if st.button("Review", key=f"rv_{code_key}", use_container_width=True, disabled=locked):
                review_dialog(row)
            if st.button(f"Reviews ({info.get('review_count',0)})", key=f"rs_{code_key}",
                         use_container_width=True):
                reviews_dialog(row)
