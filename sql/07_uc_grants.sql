-- =====================================================================
-- OMOP Review Cycle :: Unity Catalog grants (run when the groups exist)
-- Model A is in effect, so the REVIEWER/APPROVER human grants below are
-- OPTIONAL (only needed if you move to Model B / on-behalf-of-user).
-- The app SP grants are already applied; included here for completeness.
--
-- Replace the catalog if promoting to a prod catalog (e.g. omop_prod).
-- Run with: ./run_sql.sh sql/07_uc_grants.sql   (edit out blocks you don't want)
-- =====================================================================
-- Groups assumed: omop-reviewers, omop-approvers, omop-curators, omop-admins

-- ---------- CURATORS: own the CDM, run the pipeline ----------
GRANT USE CATALOG ON CATALOG vjoseph_pbi_demo                       TO `omop-curators`;
GRANT ALL PRIVILEGES ON SCHEMA vjoseph_pbi_demo.omop_cdm            TO `omop-curators`;
GRANT MODIFY, SELECT, USE SCHEMA ON SCHEMA vjoseph_pbi_demo.omop_review TO `omop-curators`;

-- ---------- ADMINS: govern the assets ----------
GRANT USE CATALOG ON CATALOG vjoseph_pbi_demo                       TO `omop-admins`;
GRANT MANAGE ON SCHEMA vjoseph_pbi_demo.omop_cdm                    TO `omop-admins`;
GRANT MANAGE ON SCHEMA vjoseph_pbi_demo.omop_review                 TO `omop-admins`;

-- ---------- PIPELINE SP (set the client_id) ----------
-- GRANT USE CATALOG ON CATALOG vjoseph_pbi_demo                    TO `<PIPELINE_SP_CLIENT_ID>`;
-- GRANT SELECT, MODIFY, USE SCHEMA ON SCHEMA vjoseph_pbi_demo.omop_cdm    TO `<PIPELINE_SP_CLIENT_ID>`;
-- GRANT MODIFY, SELECT, USE SCHEMA ON SCHEMA vjoseph_pbi_demo.omop_review TO `<PIPELINE_SP_CLIENT_ID>`;

-- =====================================================================
-- MODEL B ONLY — human reviewers/approvers read at the data layer.
-- Vocab tables only (NOT the clinical PHI tables) + review views only.
-- =====================================================================
-- GRANT USE CATALOG ON CATALOG vjoseph_pbi_demo                    TO `omop-reviewers`;
-- GRANT USE SCHEMA ON SCHEMA vjoseph_pbi_demo.omop_cdm             TO `omop-reviewers`;
-- GRANT SELECT ON TABLE vjoseph_pbi_demo.omop_cdm.concept              TO `omop-reviewers`;
-- GRANT SELECT ON TABLE vjoseph_pbi_demo.omop_cdm.concept_relationship TO `omop-reviewers`;
-- GRANT SELECT ON TABLE vjoseph_pbi_demo.omop_cdm.source_to_concept_map TO `omop-reviewers`;
-- GRANT USE SCHEMA ON SCHEMA vjoseph_pbi_demo.omop_review          TO `omop-reviewers`;
-- GRANT SELECT ON VIEW vjoseph_pbi_demo.omop_review.v_worklist_app  TO `omop-reviewers`;
-- GRANT SELECT ON VIEW vjoseph_pbi_demo.omop_review.v_concept_search TO `omop-reviewers`;
-- (repeat the same block for `omop-approvers`)
