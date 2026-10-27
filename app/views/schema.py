"""OMOP Mapping Review — Process Flow & Schema reference."""
import pandas as pd
import streamlit as st
from lib import style

style.inject()
style.header("How it works",
             "The review cycle, end to end, and the tables that keep track of it.",
             eyebrow="Reference")

# ---------- Process flow (native) ----------
style.section("The review cycle")
style.flow([
    ("Find the codes that didn't map", "Automatic",
     "We scan the data and list every source code that never matched a standard concept."),
    ("Show the list to a reviewer", "App",
     "A reviewer opens the app and sees the list, with a search box to look up the right concept."),
    ("The reviewer makes the call", "Reviewer",
     "For each code, one choice: map it, add a new local code, mark it unmappable, or ask for help."),
    ("Someone else approves it", "Approver",
     "A second person signs off. You can't approve your own work, and approved codes are locked."),
    ("Apply it to the data", "Automatic",
     "The approved mapping is written back, so the code now resolves to the right concept."),
    ("See progress, then continue", "Automatic",
     "We keep a record of what changed and watch coverage climb. Fixed codes drop off the list."),
], loop="The cycle repeats with each new batch of data.")

# ---------- Table reference ----------
style.section("The tables")


def _tbl(rows):
    return pd.DataFrame(rows, columns=["column", "type", "notes"])


REVIEW = [
    ("review_id", "bigint", "unique id for the review"),
    ("code_key", "text", "the code being reviewed (table + source code)"),
    ("domain_table", "text", "CDM source table"),
    ("source_value", "text", "the local/source code under review"),
    ("source_concept_id", "integer", "source concept (0 when unmapped)"),
    ("gap_type", "text", "vocab_gap | s2cm_gap"),
    ("decision", "text", "REMAP | NEW_LOCAL_CONCEPT | UNMAPPABLE | NEEDS_INFO"),
    ("proposed_target_concept_id", "integer", "REMAP: chosen Standard concept"),
    ("proposed_target_name", "text", "REMAP: target name"),
    ("confidence", "text", "low | medium | high"),
    ("rationale", "text", "reviewer justification"),
    ("reviewer_email", "text", "attributed reviewer"),
    ("created_at", "timestamptz", "submit time"),
    ("proposed_concept_name", "text", "NEW_LOCAL_CONCEPT: name"),
    ("proposed_domain_id", "text", "NEW_LOCAL_CONCEPT: OMOP domain"),
    ("proposed_vocabulary_id", "text", "NEW_LOCAL_CONCEPT: vocabulary"),
    ("proposed_concept_class_id", "text", "NEW_LOCAL_CONCEPT: concept class"),
    ("proposed_concept_code", "text", "NEW_LOCAL_CONCEPT: concept code"),
    ("unmappable_reason", "text", "UNMAPPABLE: controlled reason"),
    ("needs_info_note", "text", "NEEDS_INFO: what's needed"),
]

CODE_STATUS = [
    ("code_key", "text", "PK, domain_table:source_value"),
    ("domain_table", "text", "CDM source table"),
    ("source_value", "text", "the local/source code"),
    ("status", "text", "where it is: open, in review, approved, committed"),
    ("review_count", "integer", "# of reviews submitted"),
    ("approver_action", "text", "APPROVE | MERGE | REJECT | RETURN"),
    ("final_target_concept_id", "integer", "approved/minted target"),
    ("final_target_name", "text", "approved target name"),
    ("approver_rationale", "text", "approver justification"),
    ("approver_email", "text", "attributed approver"),
    ("decided_at", "timestamptz", "approval time"),
    ("locked", "boolean", "true once approved (no new reviews)"),
    ("updated_at", "timestamptz", "last change"),
]

MAPPING_UPDATE_LOG = [
    ("log_id", "string", "PK"),
    ("review_id", "string", "source review"),
    ("code_key", "string", "domain_table:source_value"),
    ("domain_table", "string", "CDM source table"),
    ("source_value", "string", "the local/source code"),
    ("old_concept_id", "int", "concept before commit"),
    ("new_concept_id", "int", "concept after commit"),
    ("mapping_method", "string", "s2cm_review | ohdsi_maps_to"),
    ("approver_email", "string", "who approved"),
    ("committed_at", "timestamp", "commit time"),
]

t1, t2, t3 = st.tabs(["review (Lakebase)", "code_status (Lakebase)", "mapping_update_log (UC)"])
with t1:
    st.caption("What a reviewer proposes. One row each time someone reviews a code.")
    st.dataframe(_tbl(REVIEW), use_container_width=True, hide_index=True)
with t2:
    st.caption("Where each code stands and who approved it. One row per code.")
    st.dataframe(_tbl(CODE_STATUS), use_container_width=True, hide_index=True)
with t3:
    st.caption("A record of every change we wrote back to the data.")
    st.dataframe(_tbl(MAPPING_UPDATE_LOG), use_container_width=True, hide_index=True)
