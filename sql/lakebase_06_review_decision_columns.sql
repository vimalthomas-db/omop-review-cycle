-- =====================================================================
-- OMOP Review Cycle :: Lakebase DDL 06 — per-decision columns on review
-- Target: Lakebase (Postgres) db `omop_review`, table public.review
-- Apply with psql (NOT the SQL Warehouse runner — this is Postgres).
--
-- Extends the existing review table so every decision type can be fully
-- populated from the app form (instead of a separate table):
--   NEW_LOCAL_CONCEPT -> proposed_concept_* (mint a 2,000,000,000+ concept at commit)
--   UNMAPPABLE        -> unmappable_reason  (controlled list)
--   NEEDS_INFO        -> needs_info_note
-- REMAP keeps using proposed_target_concept_id / proposed_target_name.
-- All columns nullable; populated only for the relevant decision.
-- =====================================================================

ALTER TABLE review ADD COLUMN IF NOT EXISTS proposed_concept_name      TEXT;
ALTER TABLE review ADD COLUMN IF NOT EXISTS proposed_domain_id         TEXT;
ALTER TABLE review ADD COLUMN IF NOT EXISTS proposed_vocabulary_id     TEXT;
ALTER TABLE review ADD COLUMN IF NOT EXISTS proposed_concept_class_id  TEXT;
ALTER TABLE review ADD COLUMN IF NOT EXISTS proposed_concept_code      TEXT;
ALTER TABLE review ADD COLUMN IF NOT EXISTS unmappable_reason          TEXT;
ALTER TABLE review ADD COLUMN IF NOT EXISTS needs_info_note            TEXT;
