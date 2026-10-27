-- =====================================================================
-- OMOP Review Cycle :: 06 commit/track layer (Unity Catalog)
-- New objects that the commit pipeline writes to.
--   - mapping_release    : one row per commit run (batch audit header)
--   - mapping_update_log : per-code change detail (already exists; add release_id)
-- Run with the SQL Warehouse runner: ./run_sql.sh sql/06_commit_layer.sql
-- =====================================================================

-- batch header: one row per pipeline run
CREATE TABLE IF NOT EXISTS vjoseph_pbi_demo.omop_review.mapping_release (
  release_id        STRING,
  run_at            TIMESTAMP,
  committed_count   INT,     -- codes whose mapping was applied
  minted_count      INT,     -- new local (2-billion) concepts created
  skipped_count     INT,     -- approved codes with no mapping change (unmappable / needs-info)
  run_by            STRING,
  notes             STRING
) COMMENT 'One row per commit-pipeline run. Ties together the rows in mapping_update_log.';

-- tie each logged change back to its release
ALTER TABLE vjoseph_pbi_demo.omop_review.mapping_update_log
  ADD COLUMNS (release_id STRING);
