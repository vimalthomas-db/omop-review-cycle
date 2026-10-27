# OMOP Mapping Review Cycle — Operations & Lifecycle

*How the mapping-review program actually runs on Databricks: environments, access & grouping, the review app, how corrections reach the real `concept` / `source_to_concept_map` / clinical tables, how to tell naturally-mapped from review-mapped data, and the governance/industry practices that hold it together. Companion to "Mapping Review — Design & Best Practices."*

---

## 1. The lifecycle at a glance

```
 DEV (synthetic / sample)                          PROD (real CDM)
 ───────────────────────                           ───────────────────────
 build views, app, jobs        ── DABs deploy ──►   same code, prod catalog
 test on synthetic gaps                              run DETECT on real CDM
        │                                                   │
        │                                            worklist (aggregate, PHI-safe)
        │                                                   │
        ▼                                            ┌──────┴───────┐
 review app (dev)                                    │ REVIEW (app) │  researchers adjudicate
                                                      └──────┬───────┘  → mapping_review (proposals)
                                                             │
                                                       APPROVE (governance)
                                                             │
                                            COMMIT: write to source_to_concept_map / concept (2B)
                                                             │
                                            RE-DERIVE clinical *_concept_id  (never hand-edit)
                                                             │
                                            RE-MEASURE coverage + PROVENANCE tag (natural vs review)
                                                             │
                                            repeat each load • version each mapping release
```

The non-obvious rules that make this safe:
- **Corrections are never hand-typed onto clinical rows.** You fix the *mapping tables*, then re-derive `*_concept_id` deterministically. (§5)
- **Reviewers never write to `source_to_concept_map` directly.** They write *proposals*; a governed step commits. (§4, §6)
- **Provenance is a column, not a tag.** Per-row "natural vs review" must be data, not metadata. (§7)

---

## 2. Environments: dev vs prod

Use **separate Unity Catalog catalogs per environment**, deployed as code:

| Environment | Catalog | Contents | Who works here |
|---|---|---|---|
| **Dev** | `omop_dev` (our current `vjoseph_pbi_demo` is effectively this) | synthetic CDM + injected gaps; app under active development | engineers building the app/jobs |
| **Prod** | `omop_prod` | the real customer CDM; real worklist; real reviewer decisions | reviewers + curators + governance |

Within each catalog, **two schemas** — separation is handled by **access (grants/governed tags), not by extra schemas**:

| Schema | Contents | Exposure |
|---|---|---|
| `cdm` | raw CDM tables incl. `concept`, `concept_relationship`, `source_to_concept_map`, clinical tables | **locked** (PHI); no reviewer access |
| `review` | reviewer-facing (`v_mapping_worklist`, `v_mapping_records`, concept-search, metric views) **and** curator/governance objects (`mapping_update_log`, `mapping_release`, `approved_reviews_fed`, commit/re-derive jobs) | reviewer objects = aggregate/exposed; curator/governance objects = write-restricted to the pipeline/curators via grants |

> No separate `ops` schema. The audit/release/federation objects live in `review` but are grant-restricted (reviewers read-only or no access); the curator-only write boundary is a **grant**, not a schema.

**Promotion is via Databricks Asset Bundles (DABs):** the views, jobs, app, and grants are defined as code in git and deployed dev→prod through CI/CD. Nothing is clicked into existence in prod. Reviews happen against **prod** (the worklist must reflect real codes/counts); dev is for building, not for deciding mappings.

---

## 3. Identity, grouping & access

### 3.1 Groups (account-level, synced from the IdP via SCIM)

Group by **domain expertise**, matching the worklist's by-domain structure:

| Group | Members | Purpose |
|---|---|---|
| `omop-reviewers-conditions` | clinicians | adjudicate condition codes |
| `omop-reviewers-drugs` | pharmacists | adjudicate drug codes |
| `omop-reviewers-measurements` | lab directors | adjudicate lab/measurement codes |
| `omop-reviewers-procedures` | clinical coders | adjudicate procedure codes |
| `omop-curators` | data engineers | run detection, commit approved mappings, re-derive |
| `omop-governance` | data governance leads | approve proposals; own the audit trail |

Account groups (not workspace-local) so they're reusable across dev/prod workspaces and centrally managed in the IdP.

### 3.2 Grant model — two complementary mechanisms

**(a) Classic UC privileges (the baseline):**

```sql
-- reviewers read one worklist view; a row filter scopes it to their domain
GRANT SELECT ON VIEW omop_prod.review.v_mapping_worklist  TO `omop-reviewers`;
GRANT SELECT ON TABLE omop_prod.cdm.concept              TO `omop-reviewers`;  -- the target picker
GRANT SELECT ON TABLE omop_prod.cdm.concept_relationship TO `omop-reviewers`;  -- read-only reference

-- reviewers do NOT get direct write on s2cm. the APP's service principal writes
-- review state to Lakebase; curators commit to the CDM mapping tables.
GRANT MODIFY ON TABLE omop_prod.cdm.source_to_concept_map     TO `omop-curators`;
```

A single **dynamic view / UC row filter** enforces the domain slice via `is_account_group_member()`, so one `v_mapping_worklist` self-filters by who's querying — no separate per-domain views.

**(b) Governed tags + ABAC (the scalable model) — see §8.** Instead of grant-per-table, classify securables with governed tags (`phi=true`, `data_classification`, `environment`) and write attribute-based policies once ("deny columns tagged `phi=true` to `omop-reviewers`"). This is the modern Databricks pattern and is far more maintainable than hand-grants as the CDM grows to dozens of tables.

### 3.3 The PHI boundary (hard rule)

- Reviewers get access to the `review` schema **only** — aggregate worklist + concept picker. **Never** the `cdm` clinical tables.
- Worklist views apply **small-cell suppression** (mask counts < 11) and a **free-text PHI scan** on `source_value`.
- Any patient-level drill-down (rarely needed) is a separate, de-identified view behind `omop-reviewers-phi` with stricter grants.
- UC audit logs every access — which doubles as evidence for IRB/compliance.

---

## 4. The review app (Databricks App)

- A **Databricks App** (the future build) is the reviewer UX. It runs as a **service principal** (`omop-app-sp`); end users authenticate via SSO and the app stamps the authenticated `reviewer_email` onto each decision.
- **Reads:** the worklist view (domain-filtered to the logged-in reviewer's groups) + the concept-search view (standard concepts by domain) as the target picker.
- **Writes:** only `mapping_review` rows, only via the SP, only `review_status='proposed'`. The app never exposes `cdm` or lets a reviewer touch `source_to_concept_map`. This is why reviewers need no direct write grants — the app is the single, validated write path.
- **Dev vs prod app:** same code, two deployments (`omop_dev` / `omop_prod` via DABs). Dev app points at synthetic data for training/UAT; prod app at the real CDM.

---

## 5. How corrections reach the *actual* tables

This is the crux. Two layers get written, in order, and **the clinical layer is derived, never hand-edited.**

### 5.1 Layer 1 — the mapping tables (the source of truth for mapping)

On **approved** `mapping_review` rows, a curator-run **commit job** does:

- `REMAP` → upsert a row into `source_to_concept_map`: `(source_code, source_concept_id, target_concept_id=<proposed>, valid_start_date=today, invalid_reason=NULL)`.
- `NEW_LOCAL_CONCEPT` → insert a **custom concept** into `concept` using the OHDSI-reserved **`concept_id >= 2,000,000,000`** range (vocabulary_id e.g. `LOCAL_HOSP`), then an `s2cm` row mapping the local code to a standard concept (or, only if nothing standard fits, mark the local concept standard within your namespace).
- `UNMAPPABLE` → recorded for the audit/OHDSI-request backlog; no table change.

### 5.2 Layer 2 — the clinical `*_concept_id` columns (re-derived)

**You do not UPDATE `condition_concept_id` by hand.** The clinical concept_id is, by contract, a deterministic function:

```
*_concept_id  =  resolve(source_value, source_vocabulary, { concept_relationship, source_to_concept_map })
```

So after Layer 1 changes, a **re-derive job** recomputes `*_concept_id` for **only the affected source codes** (incremental MERGE), e.g.:

```sql
MERGE INTO omop_prod.cdm.condition_occurrence t
USING resolved_targets r            -- recomputed from the updated mapping tables
   ON t.condition_source_value = r.source_value
WHEN MATCHED THEN UPDATE SET t.condition_concept_id = r.target_concept_id;
```

Why this discipline matters: the mapping stays reproducible (re-runnable from source + mapping tables), Delta history captures the before/after, and you never get clinical rows that disagree with the mapping tables.

---

## 6. Promoting the corrections: two models

| Model | Flow | When to use |
|---|---|---|
| **Direct DB commit** | approved `mapping_review` → MERGE into prod `source_to_concept_map` → re-derive | fastest; fine for lower-stakes / internal CDMs |
| **Mappings-as-code (GitOps)** *(recommended)* | approved decisions exported to a **version-controlled mapping file** (CSV/Delta) in git → PR review → DABs deploy → `s2cm` rebuilt from the file → re-derive | reproducible, auditable, survives vocab reloads; the OHDSI-mature pattern |

Mappings-as-code is strongly preferred for a research CDM: your custom mappings become a reviewed, versioned artifact (a "mapping release") that you can pin a study to and re-apply after any OHDSI vocabulary refresh.

---

## 7. Differentiating natural vs. review-driven mappings (provenance)

**Requirement:** be able to say, for any record or any coverage number, *how* it got mapped. This is a **per-row/per-code column**, computed in the `review` layer (keep the raw CDM OMOP-compliant). Add `mapping_method` to `v_mapping_records`:

| `mapping_method` | Meaning | How detected |
|---|---|---|
| `ohdsi_maps_to` | **natural** — resolved via OHDSI's `concept_relationship` "Maps to" | a valid "Maps to" exists from `source_concept_id` |
| `s2cm_baseline` | pre-existing local mapping (before the review program) | in `source_to_concept_map`, no linked `mapping_review` |
| `s2cm_review` | **review-driven** — committed from a reviewer decision | `s2cm` row links to a committed `mapping_review.review_id` |
| `unmapped` | still `concept_id = 0` | no arrow anywhere |

Then every metric view gains a `mapping_method` dimension, so coverage is sliceable:

> "82% mapped naturally (OHDSI), 11% via researcher review, 7% still open" — and each review-mapped code traces to a reviewer, date, and rationale via `mapping_review`.

This is the differentiation you asked for, and it's auditable end-to-end through Delta history + UC lineage.

---

## 8. Databricks governed tags & ABAC — where they fit (and where they don't)

**Governed tags** (UC tag policies: admins define allowed tag keys/values and who may apply them) + **ABAC** (attribute-based access policies driven by tags) are a strong fit for this program — but for **object/column classification and access**, not per-row provenance.

**Use governed tags for:**
- **Data classification / PHI:** tag `cdm` tables and columns `phi=true`, `data_classification=restricted`; tag `review` views `data_classification=aggregate_safe`. Then one ABAC policy — *"deny SELECT on columns tagged `phi=true` to `omop-reviewers`"* — replaces dozens of per-table grants and can't be forgotten when a new table lands.
- **Environment & ownership:** `environment=dev|prod`, `data_owner=...`, `cost_center=...` for discovery and policy.
- **Trust/certification:** mark the `review` views as **Certified** so researchers know they're the sanctioned surface.
- **Lifecycle state at the asset level:** e.g. `review_program=active`.

**Do NOT use tags for** the natural-vs-review provenance of an individual record — tags are metadata on *securables* (catalog/schema/table/column), not per-row values. Per-row provenance is the `mapping_method` **column** in §7.

> Net: governed tags + ABAC = the *access & classification* backbone (scales the §3 grants); the `mapping_method` column = the *provenance* backbone. They're complementary.

---

## 9. Coexisting with OHDSI vocabulary refreshes

OHDSI ships new vocabulary versions periodically (downloaded from **ATHENA**). When the customer reloads vocab:
- Public mappings in `concept_relationship` change automatically — re-run detection; some prior gaps may now resolve naturally (`mapping_method` flips to `ohdsi_maps_to`).
- **Custom artifacts must survive the reload:** your `2-billion` local concepts and review-driven `s2cm` rows are re-applied from the **mappings-as-code** release (§6). This is the #1 reason to keep custom mappings version-controlled rather than only in the live table.
- Record `vocabulary_version` (in `cdm_source` / `vocabulary`) alongside each **mapping release version** so a study can pin both.

---

## 10. Reproducibility & versioning

- **Delta time travel** on `source_to_concept_map`, `concept`, and clinical tables → exact before/after of every commit; diff coverage across a remediation.
- **Mapping release tags** (`v1`, `v2`, …) on each committed batch → studies pin "CDM as of mapping release v3 + vocab 2024-03."
- **Unity Catalog lineage** → trace a coverage number back through the views to the tables and the commit job.
- **Audit** → `mapping_review` (who/what/when/why) + UC access logs.

---

## 11. End-to-end: one code through the whole cycle

Take `K92.2` (GI hemorrhage), 2,560 records, currently `unmapped_vocab_gap`:

1. **Detect** — surfaces on the conditions worklist, ranked by its 2,560-record impact.
2. **Assign** — visible only to `omop-reviewers-conditions`.
3. **Review** — a clinician opens it in the app, searches the concept picker, finds standard `192671` (Gastrointestinal hemorrhage), records `REMAP → 192671`, confidence high, rationale. App writes a `mapping_review` proposal stamped with their email.
4. **Approve** — governance flips `review_status` to `approved`.
5. **Commit** — curator job exports it to the mapping release (git PR), deploys, upserts `s2cm: K92.2 → 192671`.
6. **Re-derive** — MERGE recomputes `condition_concept_id = 192671` for all 2,560 rows.
7. **Re-measure** — condition coverage rises; those records now show `mapping_method = s2cm_review`.
8. **Trace** — anyone can prove those 2,560 rows were mapped by Dr. X on this date for this reason.

---

## 12. Roles & RACI (summary)

| Activity | Reviewer | Curator/DE | Governance |
|---|---|---|---|
| Detect & build worklist | I | **R/A** | C |
| Adjudicate codes | **R/A** | C | I |
| Approve proposals | I | C | **R/A** |
| Commit to s2cm / concept | I | **R/A** | A |
| Re-derive clinical concept_ids | I | **R/A** | I |
| Provenance & audit | I | R | **R/A** |

*(R=Responsible, A=Accountable, C=Consulted, I=Informed)*

---

## 13. Build checklist (what to implement next)

1. Faithful `concept_relationship` ("Maps to") table → enables true `ohdsi_maps_to` vs `s2cm_*` provenance. *(In our demo only — the customer already has it from ATHENA.)*
2. Worklist hardening: small-cell suppression (<11) + free-text PHI scan + domain scoping via `is_account_group_member()` row filter (one view, not per-domain views).
3. Concept-search view (standard concepts by domain) = the target picker.
4. `mapping_review` table + the app's service-principal write path.
5. Commit job (mappings-as-code preferred) + incremental re-derive (MERGE) job.
6. `mapping_method` provenance column on `v_mapping_records` + metric-view dimension.
7. Governed tags (`phi`, `data_classification`, `environment`, `certified`) + ABAC policies; account groups + grants.
8. DABs project (dev/prod) for views, jobs, app, grants.
9. The reviewer app; later, integrate with the Pulse app.

---

## One-paragraph summary

The review cycle runs as code across two Unity Catalog catalogs (`omop_dev`/`omop_prod`) deployed via DABs. Researchers, grouped by clinical domain via IdP-synced account groups, log into a Databricks App (running as a service principal) that exposes only an aggregate, PHI-safe worklist and a standard-concept picker; their decisions land as proposals in a `mapping_review` table — they never touch the raw CDM or the mapping tables directly. Governance approves; a curator commits approved mappings (mappings-as-code, version-controlled) to `source_to_concept_map` or to 2-billion-range local concepts; the clinical `*_concept_id` columns are then **re-derived deterministically**, never hand-edited. Every record carries a `mapping_method` provenance column distinguishing OHDSI-natural from review-driven mappings, while Databricks governed tags + ABAC classify and protect the assets and Delta time travel + mapping-release versioning make the whole thing reproducible and auditable.
## 14. App Architecture (reviewed design)

The concrete design of the reviewer/approver application and its pipeline, incorporating the 10 review decisions.

### 14.1 Two data planes

```
Databricks App  (runs as service principal omop-app-sp; users via SSO)
 │
 ├── READ  via SQL Warehouse → Unity Catalog
 │      • worklist view (codes with standard_concept_id = 0, by domain)
 │      • concept search/picker (standard concepts only, by domain)
 │      • concept_relationship + source_to_concept_map (read-only reference)
 │
 └── READ/WRITE via Postgres → Lakebase   (OLTP review state)
        • review, code_review_status, approval

Lakebase ──(federated query, periodic)──► Commit Pipeline (UC / Delta)
        1. upsert source_to_concept_map (+ mint 2-billion concept for NEW_LOCAL_CONCEPT)
        2. RE-DERIVE clinical *_concept_id via MERGE (affected source_values only)
        3. write mapping_update_log (provenance, keyed by review_id)
        → committed codes fall off the worklist on next refresh
```

**UC = analytical surface + system of record for mappings. Lakebase = transactional review state. Pipeline bridges them.**

### 14.2 The worklist view (corrected)

Trigger = **`standard_concept_id = 0`** (NOT "both ids missing"). One row per distinct source code, per domain:

| Column | Notes |
|---|---|
| domain_table | routes to reviewer group |
| source_value | the code |
| source_description | human-readable |
| gap_type | `vocab_gap` (source_concept_id>0) / `s2cm_gap` (source_concept_id=0) |
| pct_of_unmapped_domain | **headline priority metric** (% of unmapped records in this domain) |
| record_count | **suppressed if < 11** (show "<11" or a bucket) |
| patient_count | suppressed if < 11 |

Worklist excludes codes whose Lakebase status is `in_review/reviewed/approved/committed` (no double-review), and committed codes drop off permanently after re-derivation.

*(Optional second bucket: mapped-but-non-standard — `standard_concept_id <> 0` but target is non-standard.)*

### 14.3 App pages & buttons

- **Worklist page** (per domain): the table above. Each row has a **Map** button and a **Reviews** button.
- **Map** → opens the feedback form (14.4). Writes a `review` row to Lakebase.
- **Reviews** → shows all reviews for that code (visible, attributed, timestamped) + the current status. Reviews are visible to build shared knowledge; each is attributed so anchoring is transparent.
- **Approver page** → lists codes with ≥1 review; approver sees all reviews for a code and chooses **Approve one**, **Merge** (author a custom final entry from multiple), or **Reject/Return**. Separation of duties: the approver of a code cannot be a reviewer of that same code.

### 14.4 The Map feedback form (structured, option 3 + guided fields)

| Field | Input | Destination |
|---|---|---|
| decision | REMAP / UNMAPPABLE / NEW_LOCAL_CONCEPT / NEEDS_INFO | review record |
| target_concept_id | **picked from concept search**; validated `standard_concept='S'` AND domain matches | → s2cm target_concept_id |
| target_concept_name | auto-filled from picker | readability/audit |
| source_concept_id | pre-filled from the row | → s2cm source_concept_id |
| valid_start_date | default today | → s2cm |
| confidence | high / medium / low | review record |
| rationale | short free text | review record |

The **validation guardrail** (standard + correct domain) is what prevents recreating the non-standard-mapping bug.

### 14.5 State machine

```
open ──► in_review ──► reviewed ──► approved (LOCKED) ──► committed
                 ▲           │
                 └─ reject / return ─┘
```

- `approved` is **locked**: reviews remain visible, but no new reviews and no re-approval.
- A later change (error / vocab refresh supersedes) = a **new review cycle / new entry**, never an edit of the approved record (immutable audit).

### 14.6 Lakebase tables (OLTP)

**`review`** — one row per reviewer submission
`review_id (PK), code_key, domain_table, source_value, source_concept_id, decision, proposed_target_concept_id, proposed_target_name, confidence, rationale, reviewer_email, created_at`

**`code_review_status`** — one row per code (lifecycle + lock + worklist filter)
`code_key (PK), domain_table, source_value, status, approved_review_id, approver_email, approved_at, committed_at`

**`approval`** — one row per code final decision
`code_key, approver_action (APPROVE/MERGE/REJECT/RETURN), final_target_concept_id, approver_rationale, approver_email, decided_at, source_review_ids`

### 14.7 Commit pipeline (UC / Delta) — periodic

1. Federated read of Lakebase for `status = approved` not yet `committed`.
2. Upsert `source_to_concept_map` (update existing or insert new); for `NEW_LOCAL_CONCEPT`, first insert a `concept` row in the **2,000,000,000+** range.
3. **Re-derive** clinical `*_concept_id` for affected `source_value`s only:
   `MERGE INTO <clinical> t USING recomputed r ON t.<source_value> = r.source_value WHEN MATCHED THEN UPDATE SET t.<concept_id> = r.target_concept_id`
4. Write **`mapping_update_log`** (UC/Delta): `review_id, code_key, source_value, old_concept_id, new_concept_id, mapping_method='s2cm_review', committed_at, approver_email, mapping_release`.
5. Flip Lakebase `code_review_status.status` to `committed`.

Result: clinical concept_ids stay a deterministic function of (source_value + mapping tables); every changed record is traceable to a review and an approver; coverage measurably climbs.

### 14.8 The 10 reviewed decisions (summary)

1. Lakebase for review state (OLTP); UC/Delta for worklist + final mappings.
2. Keep multi-reviewer, approver merge, and the review-id provenance table.
3. Worklist trigger = `standard_concept_id = 0` (not both-zero); show gap_type.
4. Expose `concept` as a validated target picker.
5. Validate proposed target is Standard + correct domain (anti-bug guardrail).
6. Decision types beyond Map: REMAP / UNMAPPABLE / NEW_LOCAL_CONCEPT / NEEDS_INFO; approver can Reject/Return.
7. PHI: small-cell suppression (<11); prefer % of unmapped (domain) as the priority metric; scan source_value for free-text PHI.
8. Worklist drops mid-flight (Lakebase status) and committed (re-derivation) codes.
9. Separation of duties (approver ≠ reviewer of same code); reviews are visible + attributed (not blind).
10. Pipeline "updates the actual tables" = re-derivation (MERGE on affected codes), never hand-edit.
## 15. Table & View Inventory (minimal set for the review cycle)

Deliberately lean. The review cycle needs **one view + one audit table on the Lakehouse, and two tables on Lakebase**, on top of the CDM that already exists. Everything beyond this is either a separate analytics track or a later enhancement (see 15.5).

Status legend: **EXISTS** = already in the CDM (customer or our demo) · **NEW** = build for the cycle · **MAINTAINED** = existing CDM table the pipeline writes to.

### 15.1 Lakehouse — CDM (already exists; locked / PHI)

| Object | Status | Role in the cycle |
|---|---|---|
| `concept` | EXISTS (ATHENA) · MAINTAINED | dictionary; pipeline inserts 2-billion local concepts for NEW_LOCAL_CONCEPT |
| `concept_relationship` | EXISTS (ATHENA) | the "Maps to" arrows (links, not codes) |
| `source_to_concept_map` | EXISTS · MAINTAINED | local-code arrows; pipeline upserts approved mappings |
| clinical tables (`condition_occurrence`, `drug_exposure`, `procedure_occurrence`, `measurement`, `visit_occurrence`) | EXISTS · MAINTAINED | `*_concept_id` **re-derived** via MERGE after commit |

### 15.2 Lakehouse — NEW objects (just two)

| Object | Type | Status | Purpose | Written by |
|---|---|---|---|---|
| `v_mapping_worklist` | view (row-filtered) | **NEW** | the one review surface. Trigger = `standard_concept_id = 0`; does the union+join+aggregate itself (one row per distinct source code); columns: `gap_type`, `% of unmapped (domain)`, count (suppressed <11); domain scoping via `is_account_group_member()` row filter; excludes in-flight/committed codes | (view) |
| `mapping_update_log` | table | **NEW** | the audit/provenance table — when a code was updated, by which `review_id`: `review_id, code_key, source_value, old_concept_id, new_concept_id, mapping_method, approver_email, committed_at` | commit pipeline |

*Optional:* a thin `concept_search` view (`concept` filtered to `standard_concept='S'`) as a target-picker guardrail — or just grant the app `SELECT` on `concept` and filter in the query.

### 15.3 Lakebase (Postgres) — NEW (two tables)

Two tables because multi-reviewer means "many proposals per code" + "one status per code":

| Object | Status | Purpose | Written by |
|---|---|---|---|
| `review` | **NEW** | **many rows per code** — one per reviewer submission: decision, proposed target, confidence, rationale, reviewer_email, created_at | app (service principal) |
| `code_status` | **NEW** | **one row per code** — current status (open→in_review→reviewed→approved→committed), approver action, final target, approver_email, decided_at | app (service principal) |

### 15.4 The complete minimal set

- **Lakehouse NEW:** `v_mapping_worklist`, `mapping_update_log`. *(+ optional `concept_search` view.)*
- **Lakehouse MAINTAINED by pipeline:** `concept`, `source_to_concept_map`, the 5 clinical tables.
- **Lakebase NEW:** `review`, `code_status`.

**Rule of thumb:** in-flight/transactional (reviewer typing, status flips) → **Lakebase**; final / system-of-record / audit (CDM, mappings, worklist, log) → **Lakehouse**.

### 15.5 NOT part of the review cycle (separate / optional)

These were designed for the *measure-driven analytics* story (the Pulse OMOP tie-in) or are later enhancements. The review app does **not** need any of them:

| Object | What it is | Status |
|---|---|---|
| `v_mapping_records`, `v_mapping_coverage_by_domain` | row-level inventory + coverage scorecard | optional analytics (dashboard) |
| `gold_*_enriched`, `mv_omop_care_delivery`, `mv_omop_clinical_events`, `mv_omop_mapping_quality` | OMOP→Pulse metric views | **separate deliverable** (measure-driven analytics) |
| `mapping_release` | versioned mapping snapshots | defer — reproducibility enhancement |
| (federated read of Lakebase) | how the pipeline reads approved entries | a *query*, not a stored object |
