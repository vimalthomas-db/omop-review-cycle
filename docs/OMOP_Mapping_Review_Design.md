# OMOP Mapping Review — Design & Best Practices

*How to expose the OMOP CDM to a researcher group so they can review and help complete the mapping — safely, usefully, and in a closed loop. Companion to the two teaching docs ("6 Simple Steps" and the "Field Guide").*

---

## 0. Three reframes that drive every design decision

Before any design choice, three premises must be corrected — they change everything downstream.

1. **Unmapped is not rare.** Public codes (ICD, SNOMED, RxNorm, LOINC) almost always resolve. But real EHRs are full of **local/homegrown codes** (local lab analyzers, pharmacy order codes, custom procedure codes), and those fail constantly. In our synthetic CDM, **28–50% of records per domain are unmapped**. Expect similar at the customer. The gap is large and real.

2. **You review distinct source codes, NOT rows.** Thousands of unmapped rows for one code collapse to a single worklist line. The reviewer adjudicates the *code*; the fix propagates to every row automatically. Reviewing rows is intractable *and* exposes PHI for no benefit.

3. **Review covers two buckets, not just `0`s:**
   - **Bucket A — Unmapped** (`concept_id = 0`): supply a target.
   - **Bucket B — Mapped-but-suspect** (mapped to a *non-standard* concept, or to an overly-broad/wrong concept): confirm or correct.
   Bucket B is why review adds value even when coverage looks high.

---

## 1. The unit of review: the distinct-source-code worklist

The reviewer's screen is a **worklist**, one row per distinct source code, organized **by domain**. Each line carries everything needed to adjudicate *without* touching patient data:

| Field | Example | Purpose |
|---|---|---|
| domain / table | Condition | routes to the right reviewer (pharmacist, lab director, clinician) |
| source_value | `K92.2` | the raw code under review |
| source description | "Gastrointestinal hemorrhage, unspecified" | human-readable meaning |
| source_vocabulary | ICD10CM / LOCAL_LAB | tells reviewer if it's public or local |
| current status | `unmapped_vocab_gap` | which bucket / why it failed |
| current target (if any) | `0` or a non-standard id | what it maps to today |
| record_count / patient_count | 2,560 / 1,449 | **impact ranking** (with small-cell suppression) |
| candidate target(s) | suggested standard concept(s) | a head-start for the reviewer |

This is essentially what `vjoseph_pbi_demo.omop_review.v_mapping_worklist` already produces. Reviewers work the list **top-down by impact** (record count × clinical importance).

**Organize by domain, not "all rows":**
- Reviewer expertise is domain-specific.
- The target vocabulary differs by domain (SNOMED→conditions, RxNorm→drugs, LOINC→labs, CPT/SNOMED→procedures).
- A unified cross-domain view still exists for leadership to see overall coverage and prioritize.

---

## 2. PHI & governance — the part that protects you

The good news: **a worklist of codes + counts is aggregate data, not identifiable.** So the default review surface is PHI-safe by construction. The discipline:

- **Default to aggregate-only.** Expose distinct codes + descriptions + counts. **Never** ship patient-level rows to the broad researcher group.
- **Small-cell suppression.** Mask any `record_count` / `patient_count` below a threshold (commonly **< 11**, aligned to HIPAA Safe-Harbor practice). A rare-disease code with 2 patients can be re-identifying.
- **Scan `source_value` for free-text PHI.** Most source values are clean codes, but some local "codes" are free text that could embed a name/date/MRN. Filter or flag these before exposure.
- **Gate patient-level drill-down.** If a reviewer ever needs to see example records to understand a code's context, that view is a *separate* asset behind **stricter Unity Catalog grants** (only reviewers with PHI clearance), and ideally de-identified.
- **Unity Catalog is the enabler.** Researchers get `SELECT` on the **review views only**, not the raw clinical tables. Use UC row/column masking and dynamic views. All access is audit-logged — which doubles as the review audit trail.

> Net: the broad researcher group sees a governed, aggregate, PHI-safe worklist. The raw CDM stays locked down. UC does the enforcement.

---

## 3. What the reviewer can actually DO (and what they can't)

The reviewer supplies the one thing only a human can: **the clinically-correct target** (the missing arrow). For each code they record a **decision**:

| Decision | Meaning | Downstream action |
|---|---|---|
| `APPROVE_CURRENT` | the existing mapping is correct | none — confirms quality |
| `REMAP` | map to a different standard concept (provides the target) | stage a new mapping |
| `UNMAPPABLE` | no suitable standard concept exists | document; possibly request a new OHDSI concept |
| `NEW_LOCAL_CONCEPT` | local code needs a custom concept (2-billion range) | create custom concept + mapping |
| `NEEDS_INFO` | can't decide without more context | route back for clarification |

To choose a `REMAP` target, the reviewer needs a **concept search** — a read-only, searchable view of the `concept` table filtered to **Standard concepts in the right domain** (an ATHENA-style picker). This is why we expose `concept` (read-only) as part of the tool.

What reviewers do **NOT** do: write directly to `source_to_concept_map` or edit `concept_relationship`. Those are governed/upstream. Reviewers *propose*; a controlled process *commits* (see §5).

---

## 4. Which tables to expose, and at what access level

| Table | Reviewer access | Why |
|---|---|---|
| `v_mapping_worklist` (review view) | **READ** | the worklist they work from (aggregate, PHI-safe) |
| `concept` | **READ** (searchable picker) | to find the correct standard target for a `REMAP` |
| `concept_relationship` | **READ** (reference) | to inspect existing "Maps to" arrows; they don't edit OHDSI's public arrows |
| `source_to_concept_map` | **NO direct write** | this is governed *output*, not an editing surface |
| `mapping_review` (new) | **WRITE** (their own decisions) | where reviewer input is captured |
| raw clinical tables (`condition_occurrence`, …) | **NO** (or gated, de-identified) | PHI risk; not needed for code-level review |

---

## 5. The closed loop (this is what makes it an "exercise," not a report)

```
1. DETECT    machine scans CDM -> v_mapping_worklist (unmapped + suspect codes, ranked)
                 |
2. ASSIGN    route each domain's worklist to the right reviewer group (UC grants)
                 |
3. REVIEW    reviewer adjudicates each code -> writes a row to mapping_review
                 |   (proposed target, decision, confidence, rationale, reviewer, timestamp)
                 |
4. APPROVE   a curator/governance step reviews proposals (optional 2nd sign-off)
                 |
5. COMMIT    approved REMAP/NEW_LOCAL_CONCEPT rows are written into source_to_concept_map
                 |   (and custom concepts created in the 2-billion range if needed)
                 |
6. RE-RUN    reload affected records -> coverage climbs -> worklist shrinks
                 |
                 +--> repeat each data load; track coverage trend over time
```

The decisions accumulate as a **remediation backlog + audit trail** — who decided what, when, and why. That artifact is itself a deliverable the customer's data-governance team wants.

---

## 6. The `mapping_review` decision record (proposed schema)

The new table where reviewer input lands. Keyed to a source code, not a patient.

| Column | Type | Notes |
|---|---|---|
| review_id | STRING | surrogate key |
| domain_table | STRING | e.g. `condition_occurrence` |
| source_value | STRING | the code under review |
| source_vocabulary_id | STRING | ICD10CM / LOCAL_LAB / … |
| record_count | BIGINT | impact at review time (suppressed if < threshold) |
| patient_count | BIGINT | impact at review time (suppressed if < threshold) |
| current_concept_id | INT | what it maps to today (0 if unmapped) |
| current_gap_type | STRING | unmapped_vocab_gap / mapped_nonstandard / … |
| decision | STRING | APPROVE_CURRENT / REMAP / UNMAPPABLE / NEW_LOCAL_CONCEPT / NEEDS_INFO |
| proposed_target_concept_id | INT | the reviewer's chosen standard concept (for REMAP) |
| proposed_target_name | STRING | denormalized for readability/audit |
| confidence | STRING | high / medium / low |
| rationale | STRING | clinical justification (free text) |
| reviewer_email | STRING | who decided |
| reviewed_at | TIMESTAMP | when |
| review_status | STRING | proposed / approved / committed (governance state) |

---

## 7. Roles

| Role | Who | Does |
|---|---|---|
| **Curator / Data Engineer** | the customer's CDM/ETL owner (or you) | runs detection, prepares the worklist, commits approved mappings to `s2cm`, re-runs |
| **Reviewer** | researcher / clinician / pharmacist / lab director | adjudicates codes in their domain; supplies targets + rationale |
| **Approver / Governance** | data governance lead | optional second sign-off before committing; owns the audit trail |

---

## 8. What we've already built vs. what's next

**Already built (in `vjoseph_pbi_demo.omop_review`):**
- `v_mapping_records` — unified clinical-row → concept join with `gap_type`
- `v_mapping_coverage_by_domain` — the headline scorecard
- `v_mapping_worklist` — the distinct-source-code worklist (the review surface)
- 3 metric views (care delivery, clinical events, mapping quality)

**To build for the review cycle:**
1. A faithful `concept_relationship` ("Maps to") table so public vs. local resolution mirrors a real CDM.
2. Small-cell suppression + a free-text PHI scan on the worklist view.
3. A **concept-search** view (Standard concepts by domain) as the reviewer's target picker.
4. The `mapping_review` decision table (schema above) + UC grants (reviewers write only their rows).
5. The **commit** job: approved decisions → `source_to_concept_map`; re-run; coverage trend.
6. The reviewer UX (later) — a new app over these objects; eventually integrate with the Pulse app.

---

## One-paragraph summary for the customer

We expose, per clinical domain, a governed and PHI-safe **worklist of distinct source codes** that are unmapped or suspiciously mapped, ranked by patient/record impact. Researchers log into Unity Catalog and, using a built-in standard-concept search, record a **decision** for each code (approve / re-map to a specific standard concept / unmappable / needs a local concept) with a rationale. Those decisions are captured in an auditable review table, approved by governance, and committed to `source_to_concept_map`; the CDM is reloaded and coverage measurably improves. The loop repeats every data load, turning a one-time complaint ("the mapping feels incomplete") into a continuously-improving, measurable, auditable process.
