-- =====================================================================
-- OMOP Review Cycle :: 02 review/semantic layer (schema omop_review)
-- Kept SEPARATE from raw omop_cdm. Contains:
--   - gold_*_enriched  : CDM + resolved concept names + is_mapped + gap_type
--   - v_mapping_records: unified long-format mapping inventory (all domains)
--   - v_mapping_worklist        : distinct source codes ranked by gap impact
--   - v_mapping_coverage_by_domain : the headline scorecard
-- gap_type taxonomy (the heart of the review):
--   mapped_standard      concept_id>0 and target is a Standard ('S') concept   GOOD
--   mapped_nonstandard   concept_id>0 but target is NON-standard               ETL bug
--   unmapped_vocab_gap   concept_id=0 but source recognized (source_concept_id>0) -> no std map / expired
--   unmapped_s2cm_gap    concept_id=0 and source_concept_id=0 -> code never mapped
-- =====================================================================

CREATE SCHEMA IF NOT EXISTS vjoseph_pbi_demo.omop_review
  COMMENT 'OMOP Review Cycle semantic + mapping-completeness layer over omop_cdm';

-- ---------- GOLD: visit (care delivery / LOS) ----------
CREATE OR REPLACE VIEW vjoseph_pbi_demo.omop_review.gold_visit_enriched AS
SELECT
  v.visit_occurrence_id, v.person_id,
  v.visit_concept_id, c.concept_name AS visit_type_name,
  v.visit_source_value, v.visit_source_concept_id,
  v.visit_start_date, v.visit_end_date,
  datediff(v.visit_end_date, v.visit_start_date)                                AS los_days,
  (v.visit_concept_id > 0)                                                      AS is_mapped,
  CASE
    WHEN v.visit_concept_id > 0 AND c.standard_concept = 'S' THEN 'mapped_standard'
    WHEN v.visit_concept_id > 0 THEN 'mapped_nonstandard'
    WHEN v.visit_source_concept_id > 0 THEN 'unmapped_vocab_gap'
    ELSE 'unmapped_s2cm_gap'
  END                                                                          AS gap_type
FROM vjoseph_pbi_demo.omop_cdm.visit_occurrence v
LEFT JOIN vjoseph_pbi_demo.omop_cdm.concept c ON v.visit_concept_id = c.concept_id;

-- ---------- UNIFIED MAPPING RECORDS (all 5 domains) ----------
CREATE OR REPLACE VIEW vjoseph_pbi_demo.omop_review.v_mapping_records AS
WITH unioned AS (
  SELECT 'visit_occurrence' AS domain_table, 'Visit' AS omop_domain,
         visit_occurrence_id AS record_id, person_id, visit_start_date AS event_date,
         visit_source_value AS source_value, visit_source_concept_id AS source_concept_id,
         visit_concept_id AS concept_id
  FROM vjoseph_pbi_demo.omop_cdm.visit_occurrence
  UNION ALL
  SELECT 'condition_occurrence','Condition', condition_occurrence_id, person_id, condition_start_date,
         condition_source_value, condition_source_concept_id, condition_concept_id
  FROM vjoseph_pbi_demo.omop_cdm.condition_occurrence
  UNION ALL
  SELECT 'drug_exposure','Drug', drug_exposure_id, person_id, drug_exposure_start_date,
         drug_source_value, drug_source_concept_id, drug_concept_id
  FROM vjoseph_pbi_demo.omop_cdm.drug_exposure
  UNION ALL
  SELECT 'procedure_occurrence','Procedure', procedure_occurrence_id, person_id, procedure_date,
         procedure_source_value, procedure_source_concept_id, procedure_concept_id
  FROM vjoseph_pbi_demo.omop_cdm.procedure_occurrence
  UNION ALL
  SELECT 'measurement','Measurement', measurement_id, person_id, measurement_date,
         measurement_source_value, measurement_source_concept_id, measurement_concept_id
  FROM vjoseph_pbi_demo.omop_cdm.measurement
)
SELECT
  u.*,
  c.concept_name      AS standard_concept_name,
  c.standard_concept,
  (u.concept_id > 0)  AS is_mapped,
  CASE
    WHEN u.concept_id > 0 AND c.standard_concept = 'S' THEN 'mapped_standard'
    WHEN u.concept_id > 0 THEN 'mapped_nonstandard'
    WHEN u.source_concept_id > 0 THEN 'unmapped_vocab_gap'
    ELSE 'unmapped_s2cm_gap'
  END                 AS gap_type
FROM unioned u
LEFT JOIN vjoseph_pbi_demo.omop_cdm.concept c ON u.concept_id = c.concept_id;

-- ---------- HEADLINE SCORECARD: coverage by domain ----------
CREATE OR REPLACE VIEW vjoseph_pbi_demo.omop_review.v_mapping_coverage_by_domain AS
SELECT
  domain_table, omop_domain,
  count(*)                                                                   AS total_records,
  sum(CASE WHEN gap_type='mapped_standard'    THEN 1 ELSE 0 END)             AS mapped_standard,
  sum(CASE WHEN gap_type='mapped_nonstandard' THEN 1 ELSE 0 END)            AS mapped_nonstandard,
  sum(CASE WHEN gap_type='unmapped_vocab_gap' THEN 1 ELSE 0 END)            AS unmapped_vocab_gap,
  sum(CASE WHEN gap_type='unmapped_s2cm_gap'  THEN 1 ELSE 0 END)            AS unmapped_s2cm_gap,
  round(100.0*sum(CASE WHEN gap_type='mapped_standard' THEN 1 ELSE 0 END)/count(*),1) AS pct_standard_mapped,
  round(100.0*sum(CASE WHEN is_mapped=false THEN 1 ELSE 0 END)/count(*),1)            AS pct_unmapped,
  count(DISTINCT CASE WHEN is_mapped=false THEN source_value END)                     AS distinct_unmapped_codes
FROM vjoseph_pbi_demo.omop_review.v_mapping_records
GROUP BY domain_table, omop_domain;

-- ---------- REMEDIATION WORKLIST: distinct source codes, ranked ----------
CREATE OR REPLACE VIEW vjoseph_pbi_demo.omop_review.v_mapping_worklist AS
SELECT
  domain_table, omop_domain, source_value,
  max(r.source_concept_id)          AS source_concept_id,
  max(gap_type)                     AS gap_type,
  count(*)                          AS record_count,
  count(DISTINCT person_id)         AS patient_count,
  s.source_code_description,
  s.target_vocabulary_id,
  (s.source_code IS NOT NULL)       AS exists_in_s2cm,
  s.invalid_reason                  AS s2cm_invalid_reason
FROM vjoseph_pbi_demo.omop_review.v_mapping_records r
LEFT JOIN vjoseph_pbi_demo.omop_cdm.source_to_concept_map s ON r.source_value = s.source_code
WHERE r.is_mapped = false
GROUP BY domain_table, omop_domain, source_value,
         s.source_code_description, s.target_vocabulary_id, s.source_code, s.invalid_reason;
