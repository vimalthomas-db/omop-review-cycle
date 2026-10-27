-- =====================================================================
-- OMOP Review Cycle :: Lakebase DDL 00 — review state tables
-- Target: Lakebase (Postgres) database `omop_review`, schema public.
-- Apply with psql (Postgres, not the SQL warehouse runner).
-- Reconstructed 2026-10-27 from the columns read and written by
-- app/lib/lb.py and pipeline/commit_mappings.py.
-- =====================================================================

-- One row per reviewer decision on a source code.
CREATE TABLE IF NOT EXISTS review (
  review_id                   BIGSERIAL PRIMARY KEY,
  code_key                    TEXT NOT NULL,            -- '<domain_table>:<source_value>'
  domain_table                TEXT NOT NULL,
  source_value                TEXT NOT NULL,
  source_concept_id           BIGINT,
  gap_type                    TEXT,                     -- mapped_nonstandard / unmapped_vocab_gap / unmapped_s2cm_gap
  decision                    TEXT NOT NULL,            -- REMAP / UNMAPPABLE / NEW_LOCAL_CONCEPT / NEEDS_INFO
  proposed_target_concept_id  BIGINT,
  proposed_target_name        TEXT,
  confidence                  TEXT,
  rationale                   TEXT,
  reviewer_email              TEXT NOT NULL,
  created_at                  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS review_code_key_idx ON review (code_key);

-- One row per source code: its lifecycle state and the approved decision.
CREATE TABLE IF NOT EXISTS code_status (
  code_key                 TEXT PRIMARY KEY,
  domain_table             TEXT NOT NULL,
  source_value             TEXT NOT NULL,
  status                   TEXT NOT NULL DEFAULT 'open', -- open / in_review / approved / committed
  review_count             INTEGER NOT NULL DEFAULT 0,
  locked                   BOOLEAN NOT NULL DEFAULT false,
  approver_action          TEXT,                         -- APPROVE / MERGE / REJECT / RETURN
  final_target_concept_id  BIGINT,
  final_target_name        TEXT,
  approver_rationale       TEXT,
  approver_email           TEXT,
  decided_at               TIMESTAMPTZ,
  committed_at             TIMESTAMPTZ,
  updated_at               TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- Then apply lakebase_06_review_decision_columns.sql (per-decision columns on review).
