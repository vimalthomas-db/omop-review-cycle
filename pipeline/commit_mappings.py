"""OMOP Mapping Review — commit pipeline (stage 5 + 6).

Reads APPROVED, locked codes from Lakebase, applies each decision to the CDM in
Unity Catalog, and closes the loop:

  1. resolve the target concept
       - REMAP / MERGE  -> the approver's final_target_concept_id
       - NEW_LOCAL_CONCEPT -> mint a new 2,000,000,000+ standard concept from the
         reviewer's proposal
       - UNMAPPABLE / NEEDS_INFO -> no mapping change (recorded, then closed)
  2. upsert source_to_concept_map  (the durable mapping record)
  3. re-derive the clinical *_concept_id for every row using that source code
  4. write mapping_update_log (per-code provenance) + mapping_release (run header)
  5. mark the code 'committed' in Lakebase so it drops off the worklist

Idempotent: only status='approved' rows are processed; re-running is safe.

Run locally:
    cd ~/omop_review_cycle/app            # for lib/ + .venv
    DATABRICKS_PROFILE=pulse-azure PGDATABASE=omop_review \
      PATH=/opt/homebrew/opt/postgresql@16/bin:$PATH \
      ./.venv/bin/python ../pipeline/commit_mappings.py --dry-run
    # drop --dry-run to actually commit
"""
import os
import sys
import uuid
import argparse
from datetime import datetime, timezone

# reuse the app's proven connection code (lib/uc.py, lib/lb.py, lib/config.py)
APP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app")
sys.path.insert(0, APP_DIR)
from lib import uc, lb, config  # noqa: E402

CAT = config.CATALOG
CDM = f"{CAT}.omop_cdm"
REV = f"{CAT}.omop_review"

# domain table -> clinical column prefix (e.g. condition_occurrence.condition_concept_id)
PREFIX = {
    "visit_occurrence": "visit",
    "condition_occurrence": "condition",
    "drug_exposure": "drug",
    "procedure_occurrence": "procedure",
    "measurement": "measurement",
}


def _q(v) -> str:
    """SQL literal: NULL or single-quoted, escaped string."""
    if v is None:
        return "NULL"
    return "'" + str(v).replace("'", "''") + "'"


# ---------- Lakebase reads/writes ----------
def fetch_approved() -> list:
    with lb.get_conn() as c, c.cursor() as cur:
        cur.execute("""
            SELECT code_key, domain_table, source_value, final_target_concept_id,
                   final_target_name, approver_action, approver_email
            FROM code_status
            WHERE status = 'approved' AND locked = true
            ORDER BY code_key
        """)
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]


def latest_new_local(code_key: str):
    with lb.get_conn() as c, c.cursor() as cur:
        cur.execute("""
            SELECT proposed_concept_name, proposed_domain_id, proposed_vocabulary_id,
                   proposed_concept_class_id, proposed_concept_code
            FROM review
            WHERE code_key = %s AND decision = 'NEW_LOCAL_CONCEPT'
            ORDER BY created_at DESC LIMIT 1
        """, (code_key,))
        r = cur.fetchone()
        if not r:
            return None
        keys = ["name", "domain_id", "vocabulary_id", "concept_class_id", "concept_code"]
        return dict(zip(keys, r))


def mark_committed(code_key: str):
    with lb.get_conn() as c, c.cursor() as cur:
        cur.execute("""UPDATE code_status
                       SET status='committed', committed_at=now(), updated_at=now()
                       WHERE code_key=%s""", (code_key,))
        c.commit()


# ---------- Unity Catalog writes ----------
def current_concept_id(domain_table: str, source_value: str) -> int:
    p = PREFIX[domain_table]
    df = uc.run_query(
        f"SELECT max({p}_concept_id) AS cid FROM {CDM}.{domain_table} "
        f"WHERE {p}_source_value = {_q(source_value)}")
    try:
        v = df["cid"].iloc[0]
        return int(v) if v is not None and str(v) != "nan" else 0
    except Exception:
        return 0


def mint_local_concept(lc: dict) -> int:
    df = uc.run_query(
        f"SELECT coalesce(max(concept_id), 2000000000) AS m FROM {CDM}.concept "
        f"WHERE concept_id >= 2000000000")
    new_id = int(df["m"].iloc[0]) + 1
    name = lc.get("name") or "Local concept"
    dom = lc.get("domain_id") or "Observation"
    voc = lc.get("vocabulary_id") or "OMOP Extension"
    cls = lc.get("concept_class_id") or "Custom"
    code = lc.get("concept_code") or str(new_id)
    uc.run_query(f"""
        INSERT INTO {CDM}.concept
          (concept_id, concept_name, domain_id, vocabulary_id, concept_class_id,
           standard_concept, concept_code, valid_start_date, valid_end_date, invalid_reason)
        VALUES ({new_id}, {_q(name)}, {_q(dom)}, {_q(voc)}, {_q(cls)},
                'S', {_q(code)}, current_date(), DATE'2099-12-31', NULL)""")
    return new_id


def upsert_s2cm(source_value: str, target_id: int, desc=None):
    uc.run_query(f"""
        MERGE INTO {CDM}.source_to_concept_map t
        USING (SELECT {_q(source_value)} AS source_code) s
          ON t.source_code = s.source_code
        WHEN MATCHED THEN UPDATE SET
          target_concept_id = {target_id}, invalid_reason = NULL, valid_end_date = DATE'2099-12-31'
        WHEN NOT MATCHED THEN INSERT
          (source_code, source_concept_id, source_vocabulary_id, source_code_description,
           target_concept_id, target_vocabulary_id, valid_start_date, valid_end_date, invalid_reason)
          VALUES ({_q(source_value)}, 0, 'LOCAL', {_q(desc)}, {target_id}, 'SNOMED',
                  current_date(), DATE'2099-12-31', NULL)""")


def rederive(domain_table: str, source_value: str, target_id: int) -> int:
    """Set the standard concept_id on every clinical row using this source code."""
    p = PREFIX[domain_table]
    uc.run_query(
        f"UPDATE {CDM}.{domain_table} SET {p}_concept_id = {target_id} "
        f"WHERE {p}_source_value = {_q(source_value)}")


def log_change(release_id, code, old_id, new_id, method):
    uc.run_query(f"""
        INSERT INTO {REV}.mapping_update_log
          (log_id, review_id, code_key, domain_table, source_value, old_concept_id,
           new_concept_id, mapping_method, approver_email, committed_at, release_id)
        VALUES ({_q(uuid.uuid4().hex)}, NULL, {_q(code['code_key'])}, {_q(code['domain_table'])},
                {_q(code['source_value'])}, {old_id}, {new_id}, {_q(method)},
                {_q(code['approver_email'])}, current_timestamp(), {_q(release_id)})""")


def write_release(release_id, committed, minted, skipped, run_by):
    uc.run_query(f"""
        INSERT INTO {REV}.mapping_release
          (release_id, run_at, committed_count, minted_count, skipped_count, run_by, notes)
        VALUES ({_q(release_id)}, current_timestamp(), {committed}, {minted}, {skipped},
                {_q(run_by)}, NULL)""")


# ---------- orchestration ----------
def main(dry_run: bool = False) -> str:
    approved = fetch_approved()
    run_by = config.current_user_email()
    release_id = "rel_" + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    print(f"[commit] release={release_id} dry_run={dry_run} approved={len(approved)}")

    committed = minted = skipped = 0
    for code in approved:
        ck, dt, sv = code["code_key"], code["domain_table"], code["source_value"]
        if dt not in PREFIX:
            print(f"  skip {ck}: unknown domain table {dt}")
            skipped += 1
            continue

        target = code["final_target_concept_id"]
        method = "s2cm_review"

        # NEW_LOCAL_CONCEPT path: no final target, but a local-concept proposal exists
        if not target or int(target) == 0:
            lc = latest_new_local(ck)
            if lc:
                method = "new_local_concept"
                if dry_run:
                    print(f"  [dry] mint local concept + map {sv} ({dt}) — {lc.get('name')}")
                    minted += 1
                    committed += 1
                    continue
                target = mint_local_concept(lc)
                minted += 1
            else:
                # UNMAPPABLE / NEEDS_INFO — no mapping change, just close it out
                print(f"  no-op {ck}: approved with no target (unmappable / needs-info)")
                if not dry_run:
                    old = current_concept_id(dt, sv)
                    log_change(release_id, code, old, 0, "no_change")
                    mark_committed(ck)
                skipped += 1
                continue

        if dry_run:
            print(f"  [dry] map {sv} ({dt}) -> {target}  [{method}]")
            committed += 1
            continue

        old = current_concept_id(dt, sv)
        upsert_s2cm(sv, int(target), code.get("final_target_name"))
        rederive(dt, sv, int(target))
        log_change(release_id, code, old, int(target), method)
        mark_committed(ck)
        committed += 1
        print(f"  committed {sv} ({dt})  {old} -> {target}  [{method}]")

    if not dry_run and (committed or skipped):
        write_release(release_id, committed, minted, skipped, run_by)
    print(f"[commit] done: committed={committed} minted={minted} skipped={skipped}")
    return release_id


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Commit approved OMOP mapping reviews back to the CDM.")
    ap.add_argument("--dry-run", action="store_true", help="show what would change, write nothing")
    args = ap.parse_args()
    main(dry_run=args.dry_run)
