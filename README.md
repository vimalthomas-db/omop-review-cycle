# OMOP Mapping Review Cycle

A measure-driven review of OMOP CDM concept mappings, with a Databricks App where subject-matter experts review unmapped or non-standard source codes, an approver signs off, and approved decisions are committed back into the CDM with full provenance.

Built on synthetic, Synthea-style OMOP data with deliberately seeded mapping gaps. No customer data.

## How it works
1. **Detect.** A review layer unifies five clinical domains into one long-format view of every source code and how it mapped (standard, non-standard, vocabulary gap, local gap), ranked by record count. Metric views over the CDM show which clinical measures the gaps break (for example, hypertension prevalence understated by non-standard ICD-10 mappings).
2. **Review.** SMEs work a prioritized worklist in the app and propose a decision per code: REMAP, MERGE, NEW_LOCAL_CONCEPT, UNMAPPABLE or NEEDS_INFO, with a validated concept search.
3. **Approve.** An approver accepts, merges, rejects or returns each code. Separation of duties is enforced (the approver cannot be a reviewer of the same code); approved codes are locked.
4. **Commit.** `pipeline/commit_mappings.py` upserts `source_to_concept_map`, mints local concepts (2,000,000,000+) for NEW_LOCAL_CONCEPT, re-derives the clinical `*_concept_id` columns, and writes a release header plus a per-code update log.

## Layout
```
sql/        00_schema_and_vocab .. 06_commit_layer   synthetic CDM, review layer, metric views, app views, commit tables
            lakebase_00/06/07_*.sql                   Lakebase (Postgres) tables, decision columns, grants
run_sql.sh  runs a SQL file through the Statement Execution API
app/        Streamlit Databricks App: Overview, Worklist, Approve, Reference, How it works
            lib/ config.py, uc.py (Unity Catalog reads), lb.py (Lakebase reads/writes), style.py
pipeline/   commit_mappings.py (approved decisions -> CDM, with provenance)
docs/       6 Simple Steps, Field Guide, Review Design, Operations and Lifecycle, access model, flow and swimlane diagrams
```

## Rebuild
Requirements: a Unity Catalog workspace, a SQL warehouse, a Lakebase (Autoscaling) project, Databricks CLI profile, Python 3.11+.

1. Data layer: `./run_sql.sh sql/00_schema_and_vocab.sql` and so on through `sql/06_commit_layer.sql` (catalog and schemas are set in the files; default `vjoseph_pbi_demo.omop_cdm` and `omop_review`).
2. Lakebase: `databricks postgres create-project omop-review`, `CREATE DATABASE omop_review`, then with psql apply `sql/lakebase_00_tables.sql` (the `review` and `code_status` tables) and `sql/lakebase_06_review_decision_columns.sql`. Create the app service principal's Postgres role (`databricks postgres create-role ... LAKEBASE_OAUTH_V1`) and apply the grants in `sql/lakebase_07_grants.sql`.
3. App: edit `app/app.yaml` (warehouse, catalog, schema, Lakebase endpoint, host and the app service principal as PGUSER).
   - Local: `cd app && python -m venv .venv && .venv/bin/pip install -r requirements.txt && DATABRICKS_PROFILE=<profile> .venv/bin/streamlit run app.py` (Postgres 16 client on PATH for local Lakebase token generation).
   - Databricks Apps: `databricks sync app /Workspace/Users/<you>/omop-review --full` then `databricks apps deploy omop-review --source-code-path /Workspace/Users/<you>/omop-review`. Grant the app service principal USE CATALOG, USE/SELECT on both schemas, CAN_USE on the warehouse, and a Lakebase Postgres role with privileges on `review` and `code_status`.
4. Commit approved mappings: `cd app && DATABRICKS_PROFILE=<profile> PGDATABASE=omop_review .venv/bin/python ../pipeline/commit_mappings.py --dry-run`, then without `--dry-run`.

## Status
Deployed on the Pulse field workspace (redeployed 2026-10-27): app `omop-review` at https://omop-review-984752964297111.11.azure.databricksapps.com, Lakebase project `omop-review` (Postgres 17) with database `omop_review`, reading `vjoseph_pbi_demo.omop_cdm` and `omop_review`.
