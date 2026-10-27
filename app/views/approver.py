"""OMOP Mapping Review — Approver (governance)."""
import streamlit as st
from lib import lb, config, style

style.inject()
style.header("Approve",
             "Sign off on reviewed codes: approve a proposal, enter your own target, or send it back. "
             "You can't approve a code you reviewed yourself.",
             eyebrow="Governance")

with st.sidebar:
    st.header("Approver")
    approver_email = st.text_input("Your email", value=config.current_user_email())

try:
    codes = lb.codes_for_approver()
except Exception as e:
    st.error(f"Could not load codes from Lakebase: {e}")
    st.stop()

if not codes:
    st.success("Nothing awaiting approval — all reviewed codes are decided.")
    st.stop()

labels = {f"{c['source_value']} · {c['domain_table'].split('_')[0]} · "
          f"{c['review_count']} review(s) · {c['status']}": c for c in codes}
pick = st.selectbox("Codes awaiting a decision", list(labels))
code = labels[pick]
code_key = code["code_key"]

revs = lb.get_reviews(code_key)
reviewers = lb.reviewers_of(code_key)

style.section(f"Reviews for {code['source_value']}")
for r in revs:
    tgt = f" → <b>{r['proposed_target_concept_id']}</b> ({r['proposed_target_name']})" \
          if r["proposed_target_concept_id"] else ""
    st.markdown(
        f"<div class='card'><b>{r['decision']}</b>{tgt} "
        f"<span class='chip' style='color:{style.TEAL};border-color:{style.TEAL}'>{r['confidence']}</span>"
        f"<br><span class='meta'>{r['reviewer_email']} · {r['created_at']:%Y-%m-%d %H:%M}</span>"
        f"<br>{r['rationale'] or ''}</div>", unsafe_allow_html=True)

sod = approver_email in reviewers
if sod:
    st.error("You reviewed this code — separation of duties prevents you from approving it.")

style.section("Decision")
action = st.radio("Action", ["APPROVE", "MERGE", "REJECT", "RETURN"], horizontal=True)
final_id, final_name = None, None
if action == "APPROVE":
    remaps = [r for r in revs if r["proposed_target_concept_id"]]
    if remaps:
        opts = {f"{r['proposed_target_concept_id']} ({r['proposed_target_name']}) — {r['reviewer_email']}": r
                for r in remaps}
        ch = opts[st.selectbox("Approve which proposed target?", list(opts))]
        final_id, final_name = ch["proposed_target_concept_id"], ch["proposed_target_name"]
    else:
        st.info("No REMAP targets proposed — use MERGE to author one, or REJECT/RETURN.")
elif action == "MERGE":
    final_id = st.number_input("Custom target concept_id", min_value=0, step=1)
    final_name = st.text_input("Custom target name")

rationale = st.text_area("Approver rationale")
can = (not sod) and (action not in ("APPROVE", "MERGE") or final_id)
if st.button("Submit decision", type="primary", disabled=not can, use_container_width=True):
    try:
        lb.approve(code_key, action, int(final_id) if final_id else None, final_name, rationale, approver_email)
        st.toast(f"{action} recorded")
        st.rerun()
    except Exception as e:
        st.error(f"Failed: {e}")
