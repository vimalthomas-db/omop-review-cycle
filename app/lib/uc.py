"""Unity Catalog reads via the Statement Execution API (worklist, coverage, concept picker)."""
import pandas as pd
from . import config


def run_query(sql: str) -> pd.DataFrame:
    w = config.ws()
    resp = w.statement_execution.execute_statement(
        warehouse_id=config.WAREHOUSE_ID, statement=sql, wait_timeout="50s"
    )
    if resp.status and resp.status.state.value != "SUCCEEDED":
        msg = resp.status.error.message if resp.status.error else "unknown error"
        raise RuntimeError(f"UC query failed: {msg}")
    cols = [c.name for c in resp.manifest.schema.columns] if resp.manifest else []
    rows = resp.result.data_array if (resp.result and resp.result.data_array) else []
    return pd.DataFrame(rows, columns=cols)


def _num(df, cols):
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def get_worklist() -> pd.DataFrame:
    df = run_query(f"""
        SELECT domain_table, omop_domain, source_value, source_concept_id, gap_type,
               source_code_description, exists_in_s2cm, s2cm_invalid_reason,
               record_count, patient_count, pct_of_unmapped_domain, record_count_display
        FROM {config.CATALOG}.{config.SCHEMA}.v_worklist_app
        ORDER BY omop_domain, record_count DESC
    """)
    return _num(df, ["record_count", "patient_count", "pct_of_unmapped_domain", "source_concept_id"])


def get_coverage() -> pd.DataFrame:
    df = run_query(f"""
        SELECT omop_domain, total_records, mapped_standard, mapped_nonstandard,
               unmapped_vocab_gap, unmapped_s2cm_gap, pct_standard_mapped, pct_unmapped,
               distinct_unmapped_codes
        FROM {config.CATALOG}.{config.SCHEMA}.v_mapping_coverage_by_domain
        ORDER BY pct_unmapped DESC
    """)
    return _num(df, ["total_records", "mapped_standard", "mapped_nonstandard", "unmapped_vocab_gap",
                     "unmapped_s2cm_gap", "pct_standard_mapped", "pct_unmapped", "distinct_unmapped_codes"])


def search_concepts(domain: str, term: str, limit: int = 25) -> pd.DataFrame:
    term = (term or "").replace("'", "''")
    return run_query(f"""
        SELECT concept_id, concept_name, domain_id, vocabulary_id, concept_code
        FROM {config.CATALOG}.{config.SCHEMA}.v_concept_search
        WHERE domain_id = '{domain}'
          AND (lower(concept_name) LIKE lower('%{term}%') OR concept_code = '{term}')
        ORDER BY concept_name
        LIMIT {limit}
    """)


# ---------- Reference Explorer: search the 3 CDM tables (read-only) ----------
CDM = f"{config.CATALOG}.omop_cdm"


def ref_concept(term: str, limit: int = 100) -> pd.DataFrame:
    t = (term or "").replace("'", "''")
    where = (f"WHERE lower(concept_name) LIKE lower('%{t}%') OR concept_code='{t}'"
             if t else "")
    return run_query(f"""
        SELECT concept_id, concept_name, domain_id, vocabulary_id, concept_class_id,
               standard_concept, concept_code
        FROM {CDM}.concept {where}
        ORDER BY standard_concept NULLS LAST, concept_name LIMIT {limit}
    """)


def ref_relationship(term: str, limit: int = 100) -> pd.DataFrame:
    t = (term or "").replace("'", "''")
    where = (f"AND (lower(c1.concept_name) LIKE lower('%{t}%') OR "
             f"lower(c2.concept_name) LIKE lower('%{t}%') OR c1.concept_code='{t}')" if t else "")
    return run_query(f"""
        SELECT cr.concept_id_1, c1.concept_name AS from_concept, cr.relationship_id,
               cr.concept_id_2, c2.concept_name AS to_concept, c2.standard_concept AS to_standard,
               cr.invalid_reason
        FROM {CDM}.concept_relationship cr
        LEFT JOIN {CDM}.concept c1 ON cr.concept_id_1 = c1.concept_id
        LEFT JOIN {CDM}.concept c2 ON cr.concept_id_2 = c2.concept_id
        WHERE cr.relationship_id = 'Maps to' {where}
        ORDER BY from_concept LIMIT {limit}
    """)


def ref_s2cm(term: str, limit: int = 100) -> pd.DataFrame:
    t = (term or "").replace("'", "''")
    where = (f"WHERE lower(source_code) LIKE lower('%{t}%') OR "
             f"lower(source_code_description) LIKE lower('%{t}%')" if t else "")
    return run_query(f"""
        SELECT source_code, source_concept_id, source_vocabulary_id, source_code_description,
               target_concept_id, target_vocabulary_id, invalid_reason
        FROM {CDM}.source_to_concept_map {where}
        ORDER BY source_code LIMIT {limit}
    """)
