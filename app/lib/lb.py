"""Lakebase (Postgres) review-state access: review + code_status tables."""
import subprocess
import psycopg
from . import config


def _pg_token() -> str:
    # In-app: SDK service principal. Local: CLI (proven path).
    try:
        cred = config.ws().postgres.generate_database_credential(endpoint=config.PG_ENDPOINT)
        if getattr(cred, "token", None):
            return cred.token
    except Exception:
        pass
    out = subprocess.run(
        ["databricks", "postgres", "generate-database-credential", config.PG_ENDPOINT,
         "-p", config.PROFILE, "-o", "json"],
        capture_output=True, text=True, check=True,
    ).stdout
    import json
    return json.loads(out)["token"]


def _host() -> str:
    if config.PG_HOST:
        return config.PG_HOST
    import json
    out = subprocess.run(
        ["databricks", "postgres", "list-endpoints",
         "projects/omop-review/branches/production", "-p", config.PROFILE, "-o", "json"],
        capture_output=True, text=True, check=True,
    ).stdout
    return json.loads(out)[0]["status"]["hosts"]["host"]


def get_conn():
    user = config.PG_USER or config.current_user_email()
    return psycopg.connect(
        host=_host(), port=config.PG_PORT, dbname=config.PG_DATABASE,
        user=user, password=_pg_token(), sslmode=config.PG_SSLMODE,
    )


# ---------- reads ----------
def code_status_map() -> dict:
    """code_key -> dict(status, review_count, locked, final_target_concept_id)."""
    with get_conn() as c, c.cursor() as cur:
        cur.execute("SELECT code_key, status, review_count, locked, final_target_concept_id FROM code_status")
        return {r[0]: dict(status=r[1], review_count=r[2], locked=r[3], final_target=r[4])
                for r in cur.fetchall()}


def get_reviews(code_key: str) -> list:
    with get_conn() as c, c.cursor() as cur:
        cur.execute("""
            SELECT review_id, decision, proposed_target_concept_id, proposed_target_name,
                   confidence, rationale, reviewer_email, created_at,
                   proposed_concept_name, proposed_domain_id, proposed_vocabulary_id,
                   proposed_concept_class_id, proposed_concept_code,
                   unmappable_reason, needs_info_note
            FROM review WHERE code_key = %s ORDER BY created_at
        """, (code_key,))
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]


def codes_for_approver() -> list:
    with get_conn() as c, c.cursor() as cur:
        cur.execute("""
            SELECT code_key, domain_table, source_value, status, review_count, locked
            FROM code_status WHERE review_count > 0 AND status <> 'committed'
            ORDER BY review_count DESC
        """)
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]


# ---------- writes ----------
def submit_review(row: dict, decision: str, target_id, target_name,
                  confidence: str, rationale: str, reviewer_email: str,
                  local_concept: dict | None = None,
                  unmappable_reason: str | None = None,
                  needs_info_note: str | None = None):
    code_key = f"{row['domain_table']}:{row['source_value']}"
    lc = local_concept or {}
    with get_conn() as c, c.cursor() as cur:
        cur.execute("""
            INSERT INTO review (code_key, domain_table, source_value, source_concept_id,
                gap_type, decision, proposed_target_concept_id, proposed_target_name,
                confidence, rationale, reviewer_email,
                proposed_concept_name, proposed_domain_id, proposed_vocabulary_id,
                proposed_concept_class_id, proposed_concept_code,
                unmappable_reason, needs_info_note)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (code_key, row["domain_table"], row["source_value"],
              int(row["source_concept_id"]) if row.get("source_concept_id") is not None else None,
              row.get("gap_type"), decision, target_id, target_name,
              confidence, rationale, reviewer_email,
              lc.get("name"), lc.get("domain_id"), lc.get("vocabulary_id"),
              lc.get("concept_class_id"), lc.get("concept_code"),
              unmappable_reason, needs_info_note))
        cur.execute("""
            INSERT INTO code_status (code_key, domain_table, source_value, status, review_count, updated_at)
            VALUES (%s,%s,%s,'in_review',1, now())
            ON CONFLICT (code_key) DO UPDATE
              SET review_count = code_status.review_count + 1,
                  status = CASE WHEN code_status.status='open' THEN 'in_review' ELSE code_status.status END,
                  updated_at = now()
        """, (code_key, row["domain_table"], row["source_value"]))
        c.commit()


def reviewers_of(code_key: str) -> set:
    with get_conn() as c, c.cursor() as cur:
        cur.execute("SELECT DISTINCT reviewer_email FROM review WHERE code_key=%s", (code_key,))
        return {r[0] for r in cur.fetchall()}


def approve(code_key: str, action: str, target_id, target_name,
            rationale: str, approver_email: str):
    new_status = "approved" if action in ("APPROVE", "MERGE") else "open"
    locked = action in ("APPROVE", "MERGE")
    with get_conn() as c, c.cursor() as cur:
        cur.execute("""
            UPDATE code_status
               SET status=%s, locked=%s, approver_action=%s, final_target_concept_id=%s,
                   final_target_name=%s, approver_rationale=%s, approver_email=%s,
                   decided_at=now(), updated_at=now()
             WHERE code_key=%s
        """, (new_status, locked, action, target_id, target_name, rationale,
              approver_email, code_key))
        c.commit()
