-- =====================================================================
-- OMOP Review Cycle :: 01 clinical tables (synthetic, gaps emerge from s2cm)
-- Concept resolution mimics a real ETL: source_value -> s2cm -> concept_id.
-- Gaps therefore appear naturally:
--   vocab gap   : s2cm target_concept_id = 0
--   expired     : s2cm invalid_reason='D' / valid_end_date in past  -> concept_id 0
--   s2cm gap    : source_value absent from s2cm                     -> both ids 0
--   non-standard: simulated ETL bug leaves concept_id = source (non-standard) concept
-- =====================================================================

-- ---------- PERSON ----------
CREATE OR REPLACE TABLE vjoseph_pbi_demo.omop_cdm.person AS
SELECT
  id + 1                                                   AS person_id,
  CASE WHEN pmod(hash(id),2)=0 THEN 8507 ELSE 8532 END     AS gender_concept_id,
  1940 + pmod(hash(id),60)                                 AS year_of_birth,
  1 + pmod(hash(id*7),12)                                  AS month_of_birth,
  1 + pmod(hash(id*13),28)                                 AS day_of_birth,
  CAST(NULL AS INT)                                        AS race_concept_id,
  CAST(NULL AS INT)                                        AS ethnicity_concept_id,
  CAST(id+1 AS STRING)                                     AS person_source_value,
  CASE WHEN pmod(hash(id),2)=0 THEN 'M' ELSE 'F' END       AS gender_source_value
FROM range(0, 2000);

-- ---------- OBSERVATION_PERIOD ----------
CREATE OR REPLACE TABLE vjoseph_pbi_demo.omop_cdm.observation_period AS
SELECT
  person_id                                               AS observation_period_id,
  person_id,
  DATE'2021-01-01'                                        AS observation_period_start_date,
  DATE'2024-06-30'                                        AS observation_period_end_date,
  44814724                                                AS period_type_concept_id
FROM vjoseph_pbi_demo.omop_cdm.person;

-- ---------- VISIT_OCCURRENCE ----------
-- visit_source_value -> visit_concept_id; ~6% land on an unmapped 'OBS' source.
CREATE OR REPLACE TABLE vjoseph_pbi_demo.omop_cdm.visit_occurrence AS
WITH base AS (
  SELECT
    id + 1                               AS visit_occurrence_id,
    1 + pmod(hash(id*3),2000)            AS person_id,
    DATE'2022-01-01' + pmod(hash(id),900) AS visit_start_date,
    pmod(hash(id*5),100)                 AS b
  FROM range(0, 8000)
),
typed AS (
  SELECT *,
    CASE WHEN b < 30 THEN 'IP' WHEN b < 55 THEN 'ER' WHEN b < 94 THEN 'OP' ELSE 'OBS' END AS visit_source_value
  FROM base
)
SELECT
  visit_occurrence_id, person_id,
  CASE visit_source_value WHEN 'IP' THEN 9201 WHEN 'OP' THEN 9202 WHEN 'ER' THEN 9203 ELSE 0 END AS visit_concept_id,
  visit_start_date,
  CASE WHEN visit_source_value='IP' THEN visit_start_date + (1 + pmod(hash(visit_occurrence_id),14))
       ELSE visit_start_date END                                                                  AS visit_end_date,
  9201                                                                                            AS visit_type_concept_id,
  CASE visit_source_value WHEN 'IP' THEN 9201 WHEN 'OP' THEN 9202 WHEN 'ER' THEN 9203 ELSE 0 END AS visit_source_concept_id,
  visit_source_value
FROM typed;

-- ---------- helper: build a clinical fact table from a source-code pool ----------
-- (we inline the pattern per domain rather than a macro, for clarity)

-- ---------- CONDITION_OCCURRENCE ----------
CREATE OR REPLACE TABLE vjoseph_pbi_demo.omop_cdm.condition_occurrence AS
WITH pool AS (
  SELECT * FROM VALUES
    (0,'E11.9'),(1,'I10'),(2,'J18.9'),(3,'I48.91'),(4,'I21.9'),
    (5,'K92.2'),(6,'N18.9'),(7,'I50.9'),(8,'LOCALDX99'),(9,'E11.9'),
    (10,'I10'),(11,'J18.9') AS p(pick, source_value)
),
base AS (
  SELECT id + 1 AS condition_occurrence_id,
         1 + pmod(hash(id*3),2000)              AS person_id,
         DATE'2022-01-01' + pmod(hash(id),900)  AS condition_start_date,
         pmod(hash(id),12)                      AS pick,
         pmod(hash(id*11),100)                  AS b
  FROM range(0, 30000)
),
j AS (
  SELECT base.*, pool.source_value,
         m.source_concept_id AS m_src, m.target_concept_id AS m_tgt,
         m.invalid_reason AS m_inv, m.valid_end_date AS m_end
  FROM base JOIN pool ON base.pick = pool.pick
  LEFT JOIN vjoseph_pbi_demo.omop_cdm.source_to_concept_map m ON pool.source_value = m.source_code
)
SELECT
  condition_occurrence_id, person_id,
  CASE
    WHEN b < 8 AND source_value IN ('E11.9','I10') THEN m_src               -- ETL bug: non-standard concept
    WHEN m_inv IS NULL AND m_end >= current_date() THEN coalesce(m_tgt,0)   -- valid map
    ELSE 0                                                                  -- vocab gap / expired / s2cm gap
  END                                                  AS condition_concept_id,
  condition_start_date,
  condition_start_date                                 AS condition_end_date,
  32020                                                AS condition_type_concept_id,
  coalesce(m_src,0)                                    AS condition_source_concept_id,
  source_value                                         AS condition_source_value
FROM j;

-- ---------- DRUG_EXPOSURE ----------
CREATE OR REPLACE TABLE vjoseph_pbi_demo.omop_cdm.drug_exposure AS
WITH pool AS (
  SELECT * FROM VALUES
    (0,'860975'),(1,'314076'),(2,'617314'),(3,'243670'),(4,'1049221'),
    (5,'LOCALABX01'),(6,'LOCALRX99'),(7,'860975'),(8,'314076'),(9,'617314') AS p(pick, source_value)
),
base AS (
  SELECT id + 1 AS drug_exposure_id,
         1 + pmod(hash(id*3),2000)              AS person_id,
         DATE'2022-01-01' + pmod(hash(id),900)  AS drug_exposure_start_date,
         pmod(hash(id),10)                      AS pick,
         pmod(hash(id*11),100)                  AS b
  FROM range(0, 40000)
),
j AS (
  SELECT base.*, pool.source_value,
         m.source_concept_id AS m_src, m.target_concept_id AS m_tgt,
         m.invalid_reason AS m_inv, m.valid_end_date AS m_end
  FROM base JOIN pool ON base.pick = pool.pick
  LEFT JOIN vjoseph_pbi_demo.omop_cdm.source_to_concept_map m ON pool.source_value = m.source_code
)
SELECT
  drug_exposure_id, person_id,
  CASE WHEN m_inv IS NULL AND m_end >= current_date() THEN coalesce(m_tgt,0) ELSE 0 END AS drug_concept_id,
  drug_exposure_start_date,
  drug_exposure_start_date + (7 + pmod(hash(drug_exposure_id),84))                       AS drug_exposure_end_date,
  38000177                                                                               AS drug_type_concept_id,
  coalesce(m_src,0)                                                                      AS drug_source_concept_id,
  source_value                                                                           AS drug_source_value
FROM j;

-- ---------- PROCEDURE_OCCURRENCE ----------
CREATE OR REPLACE TABLE vjoseph_pbi_demo.omop_cdm.procedure_occurrence AS
WITH pool AS (
  SELECT * FROM VALUES
    (0,'71046'),(1,'90935'),(2,'93000'),(3,'44950'),(4,'LOCALPROC9'),
    (5,'71046'),(6,'93000') AS p(pick, source_value)
),
base AS (
  SELECT id + 1 AS procedure_occurrence_id,
         1 + pmod(hash(id*3),2000)              AS person_id,
         DATE'2022-01-01' + pmod(hash(id),900)  AS procedure_date,
         pmod(hash(id),7)                       AS pick
  FROM range(0, 15000)
),
j AS (
  SELECT base.*, pool.source_value,
         m.source_concept_id AS m_src, m.target_concept_id AS m_tgt,
         m.invalid_reason AS m_inv, m.valid_end_date AS m_end
  FROM base JOIN pool ON base.pick = pool.pick
  LEFT JOIN vjoseph_pbi_demo.omop_cdm.source_to_concept_map m ON pool.source_value = m.source_code
)
SELECT
  procedure_occurrence_id, person_id,
  CASE WHEN m_inv IS NULL AND m_end >= current_date() THEN coalesce(m_tgt,0) ELSE 0 END AS procedure_concept_id,
  procedure_date,
  38000275                                                                              AS procedure_type_concept_id,
  coalesce(m_src,0)                                                                      AS procedure_source_concept_id,
  source_value                                                                           AS procedure_source_value
FROM j;

-- ---------- MEASUREMENT ----------
-- Labs intentionally have the worst mapping coverage (local codes + an unmapped LOINC).
CREATE OR REPLACE TABLE vjoseph_pbi_demo.omop_cdm.measurement AS
WITH pool AS (
  SELECT * FROM VALUES
    (0,'8480-6'),(1,'2160-0'),(2,'2345-7'),(3,'GLU-POC'),(4,'CREAT-L'),
    (5,'718-7'),(6,'8480-6'),(7,'2160-0'),(8,'GLU-POC'),(9,'CREAT-L') AS p(pick, source_value)
),
base AS (
  SELECT id + 1 AS measurement_id,
         1 + pmod(hash(id*3),2000)              AS person_id,
         DATE'2022-01-01' + pmod(hash(id),900)  AS measurement_date,
         pmod(hash(id),10)                      AS pick,
         50 + pmod(hash(id*17),150)             AS value_as_number
  FROM range(0, 50000)
),
j AS (
  SELECT base.*, pool.source_value,
         m.source_concept_id AS m_src, m.target_concept_id AS m_tgt,
         m.invalid_reason AS m_inv, m.valid_end_date AS m_end
  FROM base JOIN pool ON base.pick = pool.pick
  LEFT JOIN vjoseph_pbi_demo.omop_cdm.source_to_concept_map m ON pool.source_value = m.source_code
)
SELECT
  measurement_id, person_id,
  CASE WHEN m_inv IS NULL AND m_end >= current_date() THEN coalesce(m_tgt,0) ELSE 0 END AS measurement_concept_id,
  measurement_date,
  44818702                                                                              AS measurement_type_concept_id,
  CAST(value_as_number AS DOUBLE)                                                        AS value_as_number,
  coalesce(m_src,0)                                                                      AS measurement_source_concept_id,
  source_value                                                                           AS measurement_source_value
FROM j;
