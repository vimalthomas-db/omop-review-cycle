-- =====================================================================
-- OMOP Review Cycle :: 04 review-app data layer (the minimal set)
--   - v_worklist_app   : the one review surface (distinct unmapped source codes)
--   - v_concept_search : standard-concept target picker
--   - mapping_update_log : audit/provenance of committed changes
-- =====================================================================

-- ---------- WORKLIST (app-facing) ----------
-- One row per distinct unmapped source code, per domain. Trigger = concept_id 0.
CREATE OR REPLACE VIEW vjoseph_pbi_demo.omop_review.v_worklist_app AS
WITH unmapped AS (
  SELECT domain_table, omop_domain, source_value, source_concept_id, gap_type,
         person_id, record_id
  FROM vjoseph_pbi_demo.omop_review.v_mapping_records
  WHERE is_mapped = false
),
agg AS (
  SELECT
    domain_table, omop_domain, source_value,
    max(source_concept_id) AS source_concept_id,
    max(gap_type)          AS gap_type,
    count(*)               AS record_count,
    count(DISTINCT person_id) AS patient_count
  FROM unmapped
  GROUP BY domain_table, omop_domain, source_value
)
SELECT
  a.domain_table,
  a.omop_domain,
  a.source_value,
  a.source_concept_id,
  a.gap_type,
  s.source_code_description,
  (s.source_code IS NOT NULL)  AS exists_in_s2cm,
  s.invalid_reason             AS s2cm_invalid_reason,
  a.record_count,
  a.patient_count,
  -- priority = share of this domain's unmapped records
  round(100.0 * a.record_count / sum(a.record_count) OVER (PARTITION BY a.omop_domain), 1) AS pct_of_unmapped_domain,
  -- small-cell suppression for display
  CASE WHEN a.record_count < 11 THEN '<11' ELSE cast(a.record_count AS string) END AS record_count_display
FROM agg a
LEFT JOIN vjoseph_pbi_demo.omop_cdm.source_to_concept_map s
  ON a.source_value = s.source_code;

-- ---------- CONCEPT SEARCH (target picker) ----------
-- Standard concepts only, by domain, for the Map form. App filters by name/code/domain.
CREATE OR REPLACE VIEW vjoseph_pbi_demo.omop_review.v_concept_search AS
SELECT concept_id, concept_name, domain_id, vocabulary_id, concept_class_id, concept_code
FROM vjoseph_pbi_demo.omop_cdm.concept
WHERE standard_concept = 'S';

-- ---------- MAPPING UPDATE LOG (audit / provenance) ----------
CREATE TABLE IF NOT EXISTS vjoseph_pbi_demo.omop_review.mapping_update_log (
  log_id            STRING,
  review_id         STRING,
  code_key          STRING,
  domain_table      STRING,
  source_value      STRING,
  old_concept_id    INT,
  new_concept_id    INT,
  mapping_method    STRING,   -- 's2cm_review'
  approver_email    STRING,
  committed_at      TIMESTAMP
) COMMENT 'Provenance of every review-driven mapping change, keyed by review_id';
