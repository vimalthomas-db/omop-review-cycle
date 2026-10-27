-- =====================================================================
-- OMOP Review Cycle :: 03 metric views (the governed semantic layer)
-- Pulse OMOP Edition. Three decoupled metric views:
--   1. mv_omop_care_delivery   visits + LOS (Pulse care-delivery measure, OMOP-sourced)
--   2. mv_omop_clinical_events condition prevalence / drug & procedure utilization /
--                              lab coverage (OMOP-native pack), sliced by omop_domain
--   3. mv_omop_mapping_quality THE REVIEW STAR: cross-domain mapping completeness
-- =====================================================================

-- 1) Care delivery (LOS / excess days analog), OMOP visit-sourced
CREATE OR REPLACE VIEW vjoseph_pbi_demo.omop_review.mv_omop_care_delivery
  WITH METRICS LANGUAGE YAML AS
$$
version: 0.1
source: vjoseph_pbi_demo.omop_review.gold_visit_enriched

dimensions:
  - name: visit_start_date
    expr: source.visit_start_date
  - name: visit_type
    expr: source.visit_type_name
  - name: visit_source_value
    expr: source.visit_source_value
  - name: gap_type
    expr: source.gap_type
  - name: is_mapped
    expr: source.is_mapped

measures:
  - name: visit_count
    expr: COUNT(DISTINCT source.visit_occurrence_id)
  - name: inpatient_count
    expr: COUNT(DISTINCT CASE WHEN source.visit_concept_id = 9201 THEN source.visit_occurrence_id END)
  - name: total_los_days
    expr: SUM(CASE WHEN source.visit_concept_id = 9201 THEN source.los_days ELSE 0 END)
  - name: avg_los_days_ip
    expr: AVG(CASE WHEN source.visit_concept_id = 9201 THEN source.los_days END)
  - name: mapped_visit_count
    expr: COUNT(DISTINCT CASE WHEN source.is_mapped THEN source.visit_occurrence_id END)
  - name: unmapped_visit_count
    expr: COUNT(DISTINCT CASE WHEN NOT source.is_mapped THEN source.visit_occurrence_id END)
  - name: mapping_rate
    expr: |
      CASE WHEN MEASURE(visit_count) > 0
           THEN MEASURE(mapped_visit_count) * 1.0 / MEASURE(visit_count)
           ELSE NULL END
$$;

-- 2) Clinical events (OMOP-native pack): prevalence / utilization / lab coverage
CREATE OR REPLACE VIEW vjoseph_pbi_demo.omop_review.mv_omop_clinical_events
  WITH METRICS LANGUAGE YAML AS
$$
version: 0.1
source: vjoseph_pbi_demo.omop_review.v_mapping_records
filter: source.omop_domain <> 'Visit'

dimensions:
  - name: omop_domain
    expr: source.omop_domain
  - name: domain_table
    expr: source.domain_table
  - name: standard_concept_name
    expr: source.standard_concept_name
  - name: source_value
    expr: source.source_value
  - name: gap_type
    expr: source.gap_type
  - name: is_mapped
    expr: source.is_mapped
  - name: event_date
    expr: source.event_date

measures:
  - name: event_count
    expr: COUNT(source.record_id)
  - name: distinct_patients
    expr: COUNT(DISTINCT source.person_id)
  - name: mapped_count
    expr: SUM(CASE WHEN source.is_mapped THEN 1 ELSE 0 END)
  - name: unmapped_count
    expr: SUM(CASE WHEN source.is_mapped THEN 0 ELSE 1 END)
  - name: mapping_rate
    expr: |
      CASE WHEN MEASURE(event_count) > 0
           THEN MEASURE(mapped_count) * 1.0 / MEASURE(event_count)
           ELSE NULL END
$$;

-- 3) Mapping quality (THE REVIEW STAR): cross-domain completeness
CREATE OR REPLACE VIEW vjoseph_pbi_demo.omop_review.mv_omop_mapping_quality
  WITH METRICS LANGUAGE YAML AS
$$
version: 0.1
source: vjoseph_pbi_demo.omop_review.v_mapping_records

dimensions:
  - name: omop_domain
    expr: source.omop_domain
  - name: domain_table
    expr: source.domain_table
  - name: gap_type
    expr: source.gap_type
  - name: is_mapped
    expr: source.is_mapped
  - name: source_value
    expr: source.source_value
  - name: standard_concept_name
    expr: source.standard_concept_name
  - name: event_date
    expr: source.event_date

measures:
  - name: record_count
    expr: COUNT(source.record_id)
  - name: patient_count
    expr: COUNT(DISTINCT source.person_id)
  - name: mapped_standard_count
    expr: SUM(CASE WHEN source.gap_type = 'mapped_standard' THEN 1 ELSE 0 END)
  - name: mapped_nonstandard_count
    expr: SUM(CASE WHEN source.gap_type = 'mapped_nonstandard' THEN 1 ELSE 0 END)
  - name: vocab_gap_count
    expr: SUM(CASE WHEN source.gap_type = 'unmapped_vocab_gap' THEN 1 ELSE 0 END)
  - name: s2cm_gap_count
    expr: SUM(CASE WHEN source.gap_type = 'unmapped_s2cm_gap' THEN 1 ELSE 0 END)
  - name: unmapped_count
    expr: SUM(CASE WHEN source.is_mapped THEN 0 ELSE 1 END)
  - name: mapping_rate
    expr: |
      CASE WHEN MEASURE(record_count) > 0
           THEN (MEASURE(record_count) - MEASURE(unmapped_count)) * 1.0 / MEASURE(record_count)
           ELSE NULL END
  - name: standard_mapping_rate
    expr: |
      CASE WHEN MEASURE(record_count) > 0
           THEN MEASURE(mapped_standard_count) * 1.0 / MEASURE(record_count)
           ELSE NULL END
$$;
