-- =====================================================================
-- OMOP Review Cycle :: 05 concept_relationship ("Maps to" arrows)
-- Makes the demo faithful: public-code resolution via concept_relationship.
-- Derived from the curated concepts + valid source_to_concept_map rows.
-- =====================================================================
CREATE OR REPLACE TABLE vjoseph_pbi_demo.omop_cdm.concept_relationship (
  concept_id_1     INT,
  concept_id_2     INT,
  relationship_id  STRING,
  valid_start_date DATE,
  valid_end_date   DATE,
  invalid_reason   STRING
);

-- 'Maps to' : source/non-standard concept -> its standard target (valid s2cm rows)
INSERT INTO vjoseph_pbi_demo.omop_cdm.concept_relationship
SELECT DISTINCT source_concept_id, target_concept_id, 'Maps to',
       DATE'2018-01-01', DATE'2099-12-31', NULL
FROM vjoseph_pbi_demo.omop_cdm.source_to_concept_map
WHERE source_concept_id > 0 AND target_concept_id > 0 AND invalid_reason IS NULL;

-- 'Mapped from' : the reverse direction
INSERT INTO vjoseph_pbi_demo.omop_cdm.concept_relationship
SELECT DISTINCT target_concept_id, source_concept_id, 'Mapped from',
       DATE'2018-01-01', DATE'2099-12-31', NULL
FROM vjoseph_pbi_demo.omop_cdm.source_to_concept_map
WHERE source_concept_id > 0 AND target_concept_id > 0 AND invalid_reason IS NULL;

-- 'Maps to' self-map for standard concepts (OMOP convention: a Standard concept maps to itself)
INSERT INTO vjoseph_pbi_demo.omop_cdm.concept_relationship
SELECT concept_id, concept_id, 'Maps to', DATE'1970-01-01', DATE'2099-12-31', NULL
FROM vjoseph_pbi_demo.omop_cdm.concept
WHERE standard_concept = 'S';
