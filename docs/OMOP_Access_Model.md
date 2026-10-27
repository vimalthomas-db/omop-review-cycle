# OMOP Mapping Review — Groups & Permissions

Access model for the OMOP concept-mapping review flow across **Unity Catalog
(Lakehouse)** and **Lakebase (Postgres)**.

> **Authorization model in effect: A — App service principal.**
> The app runs as its service principal (`omop-app-sp`, client_id
> `539dd97d-f9a4-4413-a2fc-d713159cd419`). The SP performs **all** UC reads and
> Lakebase reads/writes on behalf of every user. The app captures
> `reviewer_email` / `approver_email` and enforces separation-of-duties in
> application logic. End users therefore need **only access to the app** — no
> direct UC or Lakebase grants.
>
> Model B (on-behalf-of-user, with data-layer enforcement + domain row filters)
> is documented at the end as the hardening path for PHI/audit.

---

## 1. Principals & groups

Create these as **IdP-synced account groups** (so membership is governed in the
IdP, not Databricks).

| Group | Members | Purpose |
|---|---|---|
| `omop-reviewers` *(optionally per-domain: `omop-reviewers-conditions`, `-drugs`, `-procedures`, `-measurements`, `-visits`)* | Researchers / clinical SMEs | Propose mappings in the app |
| `omop-approvers` | Governance / data stewards | Sign off on proposals (SoD) |
| `omop-curators` | Data engineers | Own the CDM build, run the commit pipeline |
| `omop-admins` | Platform owners | Manage the app, Lakebase instance, and grants |

Non-human principals:

| Principal | Identity | Role |
|---|---|---|
| **app SP** `omop-app-sp` | `539dd97d-f9a4-4413-a2fc-d713159cd419` | App runtime — reads UC, reads/writes Lakebase |
| **pipeline SP** `omop-pipeline-sp` *(recommended; or run as a curator)* | TBD | Commit pipeline — writes CDM + review-log, marks codes committed |

---

## 2. What Model A actually requires (today)

| Principal | Needs |
|---|---|
| `omop-reviewers`, `omop-approvers` | **`CAN_USE` on the app only.** Nothing in UC or Lakebase. |
| `omop-admins` | `CAN_MANAGE` on the app. |
| app SP | UC read + warehouse `CAN_USE` + Lakebase grants — **already applied** (see §5). |
| pipeline SP / curator | UC write on `omop_cdm` + `omop_review`, Lakebase read/update — apply when the commit job is scheduled (see §3, §4). |

That's the whole footprint for the running deployment. Sections 3–4 are the full
grant matrix (used now for the SPs, and for the human groups if/when you move to
Model B).

---

## 3. Lakehouse (Unity Catalog) grant matrix

Two schemas, very different sensitivity:
- **`omop_cdm`** — patient-level PHI (clinical tables) + vocabulary tables.
- **`omop_review`** — aggregate/suppressed review layer (views + logs).

| Principal | `omop_cdm` | `omop_review` | Warehouse `148ccb90800933a1` |
|---|---|---|---|
| `omop-reviewers` | `USE SCHEMA` + **SELECT on vocab tables only** (`concept`, `concept_relationship`, `source_to_concept_map`). **Never** the clinical PHI tables. | SELECT on **views only** (`v_worklist_app`, `v_concept_search`) | `CAN_USE` |
| `omop-approvers` | same vocab-only read | SELECT on review views | `CAN_USE` |
| `omop-curators` | `ALL PRIVILEGES` (ETL, upsert s2cm, mint concepts, re-derive) | `MODIFY` | `CAN_USE` |
| `omop-admins` | `MANAGE` | `MANAGE` | `CAN_MANAGE` |
| app SP | SELECT vocab tables (Reference page) | SELECT | `CAN_USE` ✅ |
| pipeline SP | `SELECT` + `MODIFY` | `MODIFY` (`mapping_update_log`, `mapping_release`) | `CAN_USE` |

**Rule:** reviewers/approvers must never receive SELECT on the raw clinical
tables (`person`, `condition_occurrence`, …). The worklist view is the safe
surface — distinct codes, aggregated, counts < 11 suppressed.

*(In Model A the reviewer/approver UC rows above are not applied — the app SP fronts them.)*

---

## 4. Lakebase (Postgres) grant matrix

Database `omop_review`; `review` = proposals, `code_status` = state/decisions.
Each connecting principal needs a Postgres role mapped via
`LAKEBASE_OAUTH_V1` + `CONNECT` + schema `USAGE` + sequence `USAGE,SELECT`.

| Postgres role | `review` | `code_status` | Notes |
|---|---|---|---|
| app SP (`omop-app-sp`) | SELECT, INSERT, UPDATE | SELECT, INSERT, UPDATE | ✅ applied |
| pipeline SP | SELECT | SELECT, UPDATE | least-privilege — no INSERT |
| `omop-curators` / `omop-admins` | owner / superuser | owner / superuser | migrations, schema mgmt |
| `omop-reviewers` / `omop-approvers` | **Model B only:** SELECT, INSERT (reviewers) | **Model B only:** SELECT, UPDATE (approvers) | not used in Model A |

---

## 5. Already applied (app SP)

- UC: `USE CATALOG` on `vjoseph_pbi_demo`; `USE SCHEMA` + `SELECT` on
  `omop_review` and `omop_cdm`.
- Warehouse `148ccb90800933a1`: `CAN_USE`.
- Lakebase: Postgres role `omop-app-sp` (`postgres_role` = client_id),
  `CONNECT` + schema `USAGE`, `SELECT/INSERT/UPDATE` on `review`, `code_status`,
  `USAGE,SELECT` on sequences, default privileges set.

---

## 6. Hardening path (Model B)

To enforce governance at the data layer instead of in app logic:
1. Switch the app's UC reads to **on-behalf-of-user** (user authorization), so
   each query runs as the signed-in user.
2. Apply the human-group UC grants in §3.
3. Add a **UC row filter / dynamic view** on `v_worklist_app` keyed on
   `is_account_group_member('omop-reviewers-<domain>')` so each reviewer sees
   only their domain's codes.
4. Optionally move Lakebase to user-auth and apply the §4 human-group grants.
