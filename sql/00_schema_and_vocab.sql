-- =====================================================================
-- OMOP Review Cycle :: 00 schema + vocabulary
-- Catalog vjoseph_pbi_demo, schema omop_cdm (kept SEPARATE from pulse_foundation)
-- OMOP CDM v5.4 subset. Synthetic but structurally faithful vocab.
-- Mapping gaps are engineered into source_to_concept_map so the review
-- surface has real gaps to catch.
-- =====================================================================

CREATE SCHEMA IF NOT EXISTS vjoseph_pbi_demo.omop_cdm
  COMMENT 'OMOP CDM v5.4 (synthetic) for the OMOP Review Cycle mapping-completeness asset';

-- ---------- VOCABULARY METADATA ----------
CREATE OR REPLACE TABLE vjoseph_pbi_demo.omop_cdm.vocabulary (
  vocabulary_id STRING, vocabulary_name STRING, vocabulary_reference STRING,
  vocabulary_version STRING, vocabulary_concept_id INT
);
INSERT INTO vjoseph_pbi_demo.omop_cdm.vocabulary VALUES
  ('SNOMED','Systematized Nomenclature of Medicine','http://snomed.info','SNOMED 2024-03-01',44819096),
  ('RxNorm','RxNorm','http://nlm.nih.gov','RxNorm 2024-04-01',44819104),
  ('LOINC','Logical Observation Identifiers Names and Codes','http://loinc.org','LOINC 2.76',44819102),
  ('ICD10CM','ICD-10-CM','http://cdc.gov','ICD10CM 2023',44819098),
  ('CPT4','Current Procedural Terminology v4','http://ama-assn.org','CPT4 2023',44819100),
  ('Visit','OMOP Visit','OMOP','Visit 2024',44819119),
  ('None','OMOP Standardized Vocabularies','OMOP','v5.0 31-AUG-23',44819096);

CREATE OR REPLACE TABLE vjoseph_pbi_demo.omop_cdm.cdm_source (
  cdm_source_name STRING, cdm_source_abbreviation STRING, cdm_holder STRING,
  source_description STRING, source_release_date DATE, cdm_release_date DATE,
  cdm_version STRING, vocabulary_version STRING
);
INSERT INTO vjoseph_pbi_demo.omop_cdm.cdm_source VALUES
  ('Synthetic Provider EHR','SYN_EHR','Pulse OMOP Edition',
   'Synthetic OMOP CDM for mapping-review demo', DATE'2024-06-01', DATE'2024-06-10',
   'v5.4','v5.0 31-AUG-23');

-- ---------- CONCEPT (curated standard + non-standard subset) ----------
-- concept_id 0 = the OMOP "No matching concept" sentinel (unmapped marker).
CREATE OR REPLACE TABLE vjoseph_pbi_demo.omop_cdm.concept (
  concept_id INT, concept_name STRING, domain_id STRING, vocabulary_id STRING,
  concept_class_id STRING, standard_concept STRING, concept_code STRING,
  valid_start_date DATE, valid_end_date DATE, invalid_reason STRING
);
INSERT INTO vjoseph_pbi_demo.omop_cdm.concept VALUES
  (0,'No matching concept','Metadata','None','Undefined',NULL,'No matching concept',DATE'1970-01-01',DATE'2099-12-31',NULL),
  -- Visit standard concepts
  (9201,'Inpatient Visit','Visit','Visit','Visit','S','IP',DATE'1970-01-01',DATE'2099-12-31',NULL),
  (9202,'Outpatient Visit','Visit','Visit','Visit','S','OP',DATE'1970-01-01',DATE'2099-12-31',NULL),
  (9203,'Emergency Room Visit','Visit','Visit','Visit','S','ER',DATE'1970-01-01',DATE'2099-12-31',NULL),
  (262,'Emergency Room and Inpatient Visit','Visit','Visit','Visit','S','ERIP',DATE'1970-01-01',DATE'2099-12-31',NULL),
  -- Condition standard concepts (SNOMED)
  (201826,'Type 2 diabetes mellitus','Condition','SNOMED','Clinical Finding','S','44054006',DATE'1970-01-01',DATE'2099-12-31',NULL),
  (320128,'Essential hypertension','Condition','SNOMED','Clinical Finding','S','59621000',DATE'1970-01-01',DATE'2099-12-31',NULL),
  (255848,'Pneumonia','Condition','SNOMED','Clinical Finding','S','233604007',DATE'1970-01-01',DATE'2099-12-31',NULL),
  (313217,'Atrial fibrillation','Condition','SNOMED','Clinical Finding','S','49436004',DATE'1970-01-01',DATE'2099-12-31',NULL),
  (4329847,'Myocardial infarction','Condition','SNOMED','Clinical Finding','S','22298006',DATE'1970-01-01',DATE'2099-12-31',NULL),
  (316139,'Heart failure','Condition','SNOMED','Clinical Finding','S','84114007',DATE'1970-01-01',DATE'2099-12-31',NULL),
  (192671,'Gastrointestinal hemorrhage','Condition','SNOMED','Clinical Finding','S','74474003',DATE'1970-01-01',DATE'2099-12-31',NULL),
  (443767,'Chronic kidney disease','Condition','SNOMED','Clinical Finding','S','709044004',DATE'1970-01-01',DATE'2099-12-31',NULL),
  -- A NON-STANDARD condition concept (ICD10CM) used to seed non-standard mapping gaps
  (35206879,'Type 2 diabetes mellitus without complications','Condition','ICD10CM','4-char billing code',NULL,'E11.9',DATE'1970-01-01',DATE'2099-12-31',NULL),
  (45542736,'Essential (primary) hypertension','Condition','ICD10CM','3-char billing code',NULL,'I10',DATE'1970-01-01',DATE'2099-12-31',NULL),
  -- Drug standard concepts (RxNorm ingredient)
  (1503297,'metformin','Drug','RxNorm','Ingredient','S','6809',DATE'1970-01-01',DATE'2099-12-31',NULL),
  (1308216,'lisinopril','Drug','RxNorm','Ingredient','S','29046',DATE'1970-01-01',DATE'2099-12-31',NULL),
  (1545958,'atorvastatin','Drug','RxNorm','Ingredient','S','83367',DATE'1970-01-01',DATE'2099-12-31',NULL),
  (1112807,'aspirin','Drug','RxNorm','Ingredient','S','1191',DATE'1970-01-01',DATE'2099-12-31',NULL),
  (1124957,'oxycodone','Drug','RxNorm','Ingredient','S','7804',DATE'1970-01-01',DATE'2099-12-31',NULL),
  (1713332,'amoxicillin','Drug','RxNorm','Ingredient','S','723',DATE'1970-01-01',DATE'2099-12-31',NULL),
  (956874,'furosemide','Drug','RxNorm','Ingredient','S','4603',DATE'1970-01-01',DATE'2099-12-31',NULL),
  -- Procedure standard concepts (SNOMED/CPT4)
  (4163872,'Plain chest X-ray','Procedure','SNOMED','Procedure','S','399208008',DATE'1970-01-01',DATE'2099-12-31',NULL),
  (2514406,'Hemodialysis','Procedure','CPT4','CPT4','S','90935',DATE'1970-01-01',DATE'2099-12-31',NULL),
  (4051938,'Electrocardiogram','Procedure','SNOMED','Procedure','S','29303009',DATE'1970-01-01',DATE'2099-12-31',NULL),
  (4301351,'Appendectomy','Procedure','SNOMED','Procedure','S','80146002',DATE'1970-01-01',DATE'2099-12-31',NULL),
  -- Measurement standard concepts (LOINC)
  (3004249,'Systolic blood pressure','Measurement','LOINC','Clinical Observation','S','8480-6',DATE'1970-01-01',DATE'2099-12-31',NULL),
  (3012888,'Diastolic blood pressure','Measurement','LOINC','Clinical Observation','S','8462-4',DATE'1970-01-01',DATE'2099-12-31',NULL),
  (3016723,'Creatinine [Mass/volume] in Serum or Plasma','Measurement','LOINC','Lab Test','S','2160-0',DATE'1970-01-01',DATE'2099-12-31',NULL),
  (3013682,'Urea nitrogen [Mass/volume] in Serum or Plasma','Measurement','LOINC','Lab Test','S','3094-0',DATE'1970-01-01',DATE'2099-12-31',NULL),
  (3004501,'Glucose [Mass/volume] in Serum or Plasma','Measurement','LOINC','Lab Test','S','2345-7',DATE'1970-01-01',DATE'2099-12-31',NULL),
  (3000963,'Hemoglobin [Mass/volume] in Blood','Measurement','LOINC','Lab Test','S','718-7',DATE'1970-01-01',DATE'2099-12-31',NULL),
  (3023103,'Potassium [Moles/volume] in Serum or Plasma','Measurement','LOINC','Lab Test','S','2823-3',DATE'1970-01-01',DATE'2099-12-31',NULL),
  -- Gender / race standard concepts for person
  (8507,'MALE','Gender','Gender','Gender','S','M',DATE'1970-01-01',DATE'2099-12-31',NULL),
  (8532,'FEMALE','Gender','Gender','Gender','S','F',DATE'1970-01-01',DATE'2099-12-31',NULL);

-- ---------- SOURCE_TO_CONCEPT_MAP (the mapping under review) ----------
-- This is where mapping completeness lives. We engineer 4 scenarios:
--   (A) GOOD     : source_concept_id>0, target_concept_id>0 standard, valid
--   (B) VOCAB GAP: source code recognized (source_concept_id>0) but target_concept_id=0
--   (C) S2CM GAP : no row here at all -> clinical record will have source_concept_id=0
--   (D) NONSTD   : target maps to a NON-standard concept (standard_concept<>'S')
--   (E) EXPIRED  : valid mapping but invalid_reason='D' / expired end date
CREATE OR REPLACE TABLE vjoseph_pbi_demo.omop_cdm.source_to_concept_map (
  source_code STRING, source_concept_id INT, source_vocabulary_id STRING,
  source_code_description STRING, target_concept_id INT, target_vocabulary_id STRING,
  valid_start_date DATE, valid_end_date DATE, invalid_reason STRING
);
INSERT INTO vjoseph_pbi_demo.omop_cdm.source_to_concept_map VALUES
  -- Conditions (ICD10CM source -> SNOMED standard)
  ('E11.9',35206879,'ICD10CM','Type 2 diabetes mellitus w/o complications',201826,'SNOMED',DATE'2018-01-01',DATE'2099-12-31',NULL), -- A GOOD
  ('I10',45542736,'ICD10CM','Essential hypertension',320128,'SNOMED',DATE'2018-01-01',DATE'2099-12-31',NULL),                       -- A GOOD
  ('J18.9',45571423,'ICD10CM','Pneumonia, unspecified organism',255848,'SNOMED',DATE'2018-01-01',DATE'2099-12-31',NULL),           -- A GOOD
  ('I48.91',45548456,'ICD10CM','Unspecified atrial fibrillation',313217,'SNOMED',DATE'2018-01-01',DATE'2099-12-31',NULL),          -- A GOOD
  ('I21.9',45562456,'ICD10CM','Acute myocardial infarction, unspecified',4329847,'SNOMED',DATE'2018-01-01',DATE'2099-12-31',NULL), -- A GOOD
  ('K92.2',45572345,'ICD10CM','Gastrointestinal hemorrhage, unspecified',0,'SNOMED',DATE'2018-01-01',DATE'2099-12-31',NULL),        -- B VOCAB GAP (no standard target)
  ('N18.9',45576123,'ICD10CM','Chronic kidney disease, unspecified',0,'SNOMED',DATE'2018-01-01',DATE'2099-12-31',NULL),             -- B VOCAB GAP
  ('I50.9',45581234,'ICD10CM','Heart failure, unspecified',316139,'SNOMED',DATE'2010-01-01',DATE'2019-12-31','D'),                  -- E EXPIRED mapping
  -- Drugs (NDC/local source -> RxNorm standard); some map to non-standard branded concept
  ('860975',19122121,'NDC','metformin 500 MG tablet',1503297,'RxNorm',DATE'2018-01-01',DATE'2099-12-31',NULL),   -- A GOOD
  ('314076',19124220,'NDC','lisinopril 10 MG tablet',1308216,'RxNorm',DATE'2018-01-01',DATE'2099-12-31',NULL),    -- A GOOD
  ('617314',19133221,'NDC','atorvastatin 20 MG tablet',1545958,'RxNorm',DATE'2018-01-01',DATE'2099-12-31',NULL),  -- A GOOD
  ('243670',19019234,'NDC','aspirin 81 MG tablet',1112807,'RxNorm',DATE'2018-01-01',DATE'2099-12-31',NULL),       -- A GOOD
  ('1049221',19099876,'NDC','oxycodone 5 MG tablet',0,'RxNorm',DATE'2018-01-01',DATE'2099-12-31',NULL),           -- B VOCAB GAP
  ('LOCALABX01',0,'LOCAL_RX','House antibiotic mix (local code)',0,'RxNorm',DATE'2018-01-01',DATE'2099-12-31',NULL), -- C-ish: source not in std vocab
  -- Procedures (CPT4 source)
  ('71046',2212345,'CPT4','Radiologic examination, chest',4163872,'SNOMED',DATE'2018-01-01',DATE'2099-12-31',NULL), -- A GOOD
  ('90935',2514406,'CPT4','Hemodialysis procedure',2514406,'CPT4',DATE'2018-01-01',DATE'2099-12-31',NULL),          -- A GOOD (CPT4 is standard for proc)
  ('93000',2211789,'CPT4','Electrocardiogram, complete',4051938,'SNOMED',DATE'2018-01-01',DATE'2099-12-31',NULL),    -- A GOOD
  ('44950',2218900,'CPT4','Appendectomy',0,'SNOMED',DATE'2018-01-01',DATE'2099-12-31',NULL),                        -- B VOCAB GAP
  -- Measurements (LOINC source - already standard, plus local lab codes)
  ('8480-6',3004249,'LOINC','Systolic blood pressure',3004249,'LOINC',DATE'2018-01-01',DATE'2099-12-31',NULL),      -- A GOOD
  ('2160-0',3016723,'LOINC','Creatinine serum',3016723,'LOINC',DATE'2018-01-01',DATE'2099-12-31',NULL),             -- A GOOD
  ('2345-7',3004501,'LOINC','Glucose serum',3004501,'LOINC',DATE'2018-01-01',DATE'2099-12-31',NULL),                -- A GOOD
  ('GLU-POC',0,'LOCAL_LAB','Point of care glucose (local)',0,'LOINC',DATE'2018-01-01',DATE'2099-12-31',NULL),       -- C-ish local unmapped
  ('CREAT-L',0,'LOCAL_LAB','Creatinine (local analyzer code)',0,'LOINC',DATE'2018-01-01',DATE'2099-12-31',NULL);    -- C-ish local unmapped
