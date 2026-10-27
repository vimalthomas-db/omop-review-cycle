# How OMOP Mapping Actually Works

*A field guide for the OMOP Review Cycle — understand the machinery before designing the review process.*

---

## Why this matters

You can't design a good mapping-review process until you understand exactly *what* is being reviewed at each step. This doc teaches the mapping machinery from the ground up, using worked examples from the synthetic CDM we built (`vjoseph_pbi_demo.omop_cdm`). Once the mental model is in place, the review design falls out of it almost automatically.

---

## 1. The big idea: OMOP standardizes *content*, not just *structure*

Most people think OMOP = "a common schema of ~44 tables." That's only half of it. There are **two** harmonizations happening:

- **Structural harmonization** — your data goes into standard tables and columns (`condition_occurrence`, `drug_exposure`, `measurement`…). This is the easy half.
- **Semantic harmonization** — the actual *codes* in your data get translated into one shared vocabulary, so that "diabetes" means the same thing whether it came from an Epic ICD-10 code, a Cerner code, or a hospital in Germany. **This is "the mapping" — the hard half, and exactly where your customer feels incomplete.**

OMOP's entire value proposition rests on the second half: a research study written once runs unchanged across 100 hospitals worldwide *because everyone mapped their local codes to the same standard concepts*. If the mapping is wrong, that promise breaks **silently** — the query still runs, it just returns wrong numbers.

---

## 2. The atom of OMOP: the **Concept**

Everything in OMOP is a **concept** — a row in the `concept` table with a unique integer `concept_id`. A concept isn't just a disease. It's *any* coded idea:

- a diagnosis (Type 2 diabetes)
- a drug ingredient (metformin)
- a lab test (serum creatinine)
- a unit of measure (mg/dL)
- a visit type (Inpatient Visit)
- a person's gender
- a record's provenance ("EHR encounter diagnosis")
- **a geographic region or country**

That last one answers a common first question: *"why does the `location` table have `concept_id` columns?"* OMOP's rule is:

> **If a column holds a coded value, that value is a `concept_id` pointing at the `concept` table.**

In CDM v5.4, `location` has `region_concept_id` and `country_concept_id`. Geography is just another vocabulary. A US state isn't the string "Nevada" — it's a `concept_id` whose `domain_id = 'Geography'`. This is the "everything-is-a-concept" philosophy, applied even to reference/dimension data.

---

## 3. Standard vs. non-standard — the single most important distinction

Every concept carries a `standard_concept` flag:

| Flag | Meaning | Example in our data |
|---|---|---|
| `'S'` Standard | The **one** canonical concept for this idea. This is what events must be recorded as. | `201826` Type 2 diabetes (SNOMED) |
| `NULL` Non-standard | A "source" concept — a code from a source vocabulary that should be *mapped to* a standard one. | `35206879` "E11.9" (ICD-10-CM) |
| `'C'` Classification | A grouper used for hierarchy/rollups — never used to record an event directly. | an ATC / MeSH category |

**The cardinal rule:** for any clinical idea there should be exactly **one** standard concept, drawn from the vocabulary OHDSI designated as standard for that domain:

| Domain | Standard vocabulary |
|---|---|
| Condition | SNOMED |
| Drug | RxNorm / RxNorm Extension |
| Measurement / Observation | LOINC |
| Procedure | SNOMED / CPT4 / HCPCS |
| Visit | OMOP Visit |

ICD-10-CM, NDC, local codes — all **non-standard**. They exist only to be mapped onward to a standard concept.

This rule is exactly what our "money finding" violated: hypertension appeared as **both** `320128` (SNOMED, standard) **and** `45542736` (ICD-10-CM, non-standard). Two concepts for one disease → prevalence split across two rows → wrong answer for any researcher.

---

## 4. The three-column pattern (the heart of mapping)

Look at any clinical table and you'll see this trio of columns. Memorize it — it **is** mapping:

| Column | Holds | Example (a correctly mapped row) |
|---|---|---|
| `*_source_value` | the **raw code/text** from the source system (kept verbatim, forever) | `'E11.9'` |
| `*_source_concept_id` | the concept for that source code **if OMOP recognizes the source vocabulary** (else `0`) | `35206879` (the ICD-10-CM concept) |
| `*_concept_id` | the **standard** concept it maps to (else `0`) | `201826` (SNOMED T2DM) |

So one diabetes record is stored as:

```
condition_source_value      = 'E11.9'
condition_source_concept_id = 35206879   -- the ICD-10-CM (non-standard) concept
condition_concept_id        = 201826     -- the SNOMED (standard) concept
```

You keep the full provenance **and** the standardized value. Analysts query `*_concept_id`; auditors trace back through `*_source_concept_id` and `*_source_value`.

**Mapping completeness is measured directly on these columns** — which is why our entire review layer keys off two conditions: `concept_id = 0` (unmapped) and "`concept_id` points to a non-standard concept" (mis-mapped).

---

## 5. How a single record actually gets mapped (the chain)

Here is the ETL's job for one source row — ICD-10-CM `"E11.9"`:

```
"E11.9"   (raw string in the EHR)
   |  1. look up in CONCEPT where vocabulary_id='ICD10CM' and concept_code='E11.9'
   v
35206879  Type 2 diabetes w/o complications  (ICD10CM, standard_concept = NULL)   -->  source_concept_id
   |  2. follow CONCEPT_RELATIONSHIP where relationship_id = 'Maps to'
   v
201826    Type 2 diabetes mellitus  (SNOMED, standard_concept = 'S')              -->  concept_id
   |  3. the standard concept's DOMAIN decides the destination table
   v
domain_id = 'Condition'  -->  row is written to condition_occurrence
```

Two different mapping mechanisms feed this chain, and you must know **both**, because they fail in different ways:

### a) `concept_relationship` ("Maps to") — for codes already in OMOP vocabularies
Used when the source code lives in a vocabulary OMOP already ships (ICD-10-CM, NDC, CPT4, LOINC…). You download these vocabularies from **ATHENA**, and the "Maps to" rows come **pre-built by OHDSI**. The ETL simply follows them — no manual work.

### b) `source_to_concept_map` (s2cm) — for local / homegrown codes
Used for codes that aren't in any OMOP vocabulary (our `GLU-POC`, `LOCALRX99`, `LOCALDX99`). Nobody can pre-build these — **your customer's team** must author each mapping, usually with **USAGI** (a tool that suggests standard targets; a human approves them). This is where most "incompleteness" lives, because it is manual and easy to leave unfinished.

> **Demo note:** in our synthetic CDM we simplified and routed everything through `source_to_concept_map`. A real customer CDM resolves ICD/NDC/CPT/LOINC codes through `concept_relationship` ("Maps to") and reserves `source_to_concept_map` for local codes. We can add a faithful `concept_relationship` table so the demo mirrors the customer exactly.

---

## 6. Domain decides the table (and causes a whole class of errors)

Notice step 3 above: the **domain of the standard concept** — not the source system — dictates the destination table. A code mapping to a Condition concept goes to `condition_occurrence`; a Drug concept to `drug_exposure`.

A subtle, common real-world bug: an ETL that routes by *source feed* ("everything from the diagnosis feed becomes a condition") instead of by *concept domain*. A procedure code riding inside the diagnosis feed then lands in the wrong table. That's the **domain routing error** class — invisible unless you specifically check that each record's table matches its concept's domain.

---

## 7. The vocabulary tables you review against

| Table | Role |
|---|---|
| `concept` | every concept; the master dictionary |
| `concept_relationship` | links between concepts — especially **"Maps to"** (source → standard) |
| `concept_ancestor` | pre-computed hierarchy (every ancestor ↔ descendant). Powers "give me diabetes *and all its subtypes*" without recursive SQL |
| `vocabulary` | the source vocabularies loaded **and their version** (vocab drift lives here) |
| `domain` / `concept_class` | classification of concepts |
| `source_to_concept_map` | your team's **custom** local-code mappings |
| `drug_strength` | ingredient / dose math for drugs |

`concept_ancestor` is worth flagging to researchers: cohort definitions depend on it. If mapping is incomplete, descendants go missing, and a cohort like "all diabetics" silently undercounts.

---

## 8. The OHDSI toolchain (names the customer will use)

| Tool | Purpose |
|---|---|
| **ATHENA** | download standard vocabularies (source of `concept`, `concept_relationship`, etc.) |
| **USAGI** | build source → standard mappings for local codes (semi-automated + human review). *This is essentially the manual review tool we are rebuilding in Databricks.* |
| **ATLAS** | cohort building and analytics on the CDM |
| **ACHILLES** | data characterization (counts, distributions) |
| **Data Quality Dashboard (DQD)** | ~4,000 automated checks across Conformance / Completeness / Plausibility |

---

## 9. So where does "incomplete mapping" actually come from?

Every failure mode is a broken link in the chain from Section 5 — and each maps directly to the `gap_type` taxonomy we built into the review layer:

| Symptom | Broken link | Our `gap_type` | Example in our data |
|---|---|---|---|
| `concept_id = 0`, source recognized | "Maps to" missing/expired, or vocab not current | `unmapped_vocab_gap` | heart failure `I50.9` (expired map), GI bleed `K92.2` |
| `concept_id = 0`, source unknown | local code, no `source_to_concept_map` row built | `unmapped_s2cm_gap` | `GLU-POC`, `LOCALRX99` |
| `concept_id` ≠ 0 but non-standard | ETL stored `source_concept_id` instead of following "Maps to" | `mapped_nonstandard` | the hypertension / diabetes split |
| Right concept, wrong table | routed by source feed, not concept domain | domain error | (not simulated yet) |
| Counts drift over time | vocabulary version mismatch | currency issue | tracked via `vocabulary` / `cdm_source` |

---

## 10. What this means for the review design

Here is the key insight for designing the review cycle. The mapping chain has **machine-checkable links and exactly one human-only link**:

- **Hops 1, 2, 4, 5** — *Is the source recognized? Does it map? Is the target standard? Right domain? Current vocab?* — are **automatable**. Our coverage views and metric views already compute all of these.
- **Hop 3** — *"Is `E11.9` → `201826` the **clinically correct** target, and is the chosen standard concept the right one?"* — can **only be judged by a human** (the researcher / clinician). USAGI's entire reason to exist is to support this one judgment.

So the review cycle is **not** "look at unmapped counts." It is:

> The machine narrows millions of records down to a short worklist of distinct source codes (each with a current and/or candidate target and its record/patient impact). The researcher adjudicates the one thing only they can — **clinical correctness** — and that decision flows back into the mapping.

This is the irreplaceable reason your researchers must log in to Unity Catalog: they own Hop 3. Everything else, the platform does for them.

**The reviewer's screen, per source code, should therefore show:**
- the raw `source_value` + its description
- what it currently maps to, and whether that target is *standard*
- candidate standard concept(s) to map to
- record count + patient count (impact ranking)
- a place to capture the verdict (approve / re-map to X / reject / needs info)

---

## Quick glossary

- **CDM** — Common Data Model (the OMOP schema)
- **OHDSI** — Observational Health Data Sciences and Informatics (the community/standards body)
- **Concept** — any coded idea, identified by `concept_id`
- **Standard concept** — the one canonical concept for an idea (`standard_concept = 'S'`)
- **Source concept** — a non-standard concept representing a source code (e.g. ICD-10-CM)
- **Maps to** — the `concept_relationship` that links a source concept to its standard concept
- **s2cm** — `source_to_concept_map`, the custom table for local-code mappings
- **Domain** — the category (Condition, Drug, Procedure…) that determines the destination table
