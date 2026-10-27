# OMOP Mapping in 6 Simple Steps

*A slow, plain-English walkthrough using two real rows from our data. No jargon dumps. One small idea per step.*

---

## Step 1 — The problem we're solving

Your customer's hospital records a diagnosis as a **code**.

- For pneumonia, their system wrote down `J18.9`.
- For a GI bleed, it wrote `K92.2`.

These are **ICD-10** codes — the hospital's own "local language."

The problem: a *different* hospital might code pneumonia with a completely different code. And a researcher writing a study can't memorize every hospital's local codes. So research across combined data is impossible…

**…unless everyone first translates their local codes into one shared language.**

That translation is "the mapping." That is the whole game.

---

## Step 2 — The shared language is a numbered dictionary

OMOP picks one master dictionary. Every entry in it has a permanent **ID number** (called a `concept_id`). For example:

- `255848` = "Pneumonia"
- `201826` = "Type 2 diabetes mellitus"
- `192671` = "Gastrointestinal hemorrhage"

Think of it like a giant glossary where every medical idea has one permanent ID number. These shared IDs are called **standard concepts**. The goal of mapping is to get every record pointing at the right standard concept.

---

## Step 3 — Look at two real rows from our data

These are two actual rows from the synthetic CDM we built:

| raw_code | source_concept_id | standard_concept_id | num_records |
|---|---|---|---|
| J18.9 | 45571423 | 255848 | 4,933 |
| K92.2 | 45572345 | 0 | 2,560 |

There are **three columns** that matter. Here's what each one means, reading the **J18.9 (pneumonia)** row left to right:

| Column | Value | What it means |
|---|---|---|
| `raw_code` | `J18.9` | exactly what the hospital wrote down — untouched |
| `source_concept_id` | `45571423` | the dictionary's entry for *the ICD-10 code itself* ("J18.9, the ICD code") |
| `standard_concept_id` | `255848` | **the translation** — the shared "Pneumonia" entry |

So J18.9 was **successfully translated**: it found its way to `255848` = Pneumonia.
Mapping done. ✅

---

## Step 4 — Now look at the second row, K92.2 (GI bleed)

| raw_code | source_concept_id | standard_concept_id |
|---|---|---|
| K92.2 | 45572345 | **0** |

The first two columns are fine — the hospital wrote `K92.2`, and the dictionary even recognizes the ICD code (`45572345`).

But the third column — the translation — is **`0`**.

> **`0` means "no translation found."** It is OMOP's way of writing down: *"we gave up — this record never got mapped to the shared language."*

So 2,560 GI-bleed records are sitting there **untranslated**. ❌

---

## Step 5 — That `0` is the entire project

"Incomplete mapping" simply means: **too many records have `0` in that third column.**

Why it matters — a researcher studying GI bleeds writes:

```sql
WHERE standard_concept_id = 192671   -- the shared "GI hemorrhage" entry
```

Those 2,560 records have `0`, not `192671`. So they **silently disappear** from the study.

The query runs fine. It just returns a wrong, too-low number. Nobody gets an error message. **That is exactly why your customer "feels" the mapping is incomplete** — their results look off, but nothing appears broken.

---

## Step 6 — So what is "the mapping exercise"?

It is two jobs:

1. **Find the `0`s** — which raw codes never got translated, and how many records each one affects.
   *(The machine does this. Our coverage views already list every one.)*

2. **Fix them** — decide what each untranslated code *should* translate to.
   *(A human must do this. A researcher says "K92.2 should map to 192671, GI hemorrhage." A computer can't be trusted to pick the clinically-correct target — that's a medical judgment.)*

The **review cycle** we are designing is just this loop:

> machine finds the `0`s → researcher decides the right translation → we fill it in → re-check → repeat

---

## The one-sentence summary

OMOP mapping = translating every hospital's local codes into one shared numbered dictionary; a `0` means a record never got translated; the "review cycle" is the machine finding the untranslated codes and a researcher deciding the correct translation.

---

## A small glossary (only the words you need)

- **Code** — what the hospital wrote down (e.g. `J18.9`). The "local language."
- **Concept / `concept_id`** — an entry in the shared dictionary, identified by a number.
- **Standard concept** — the one official shared entry every record should point to.
- **Mapping** — the act of translating a local code to its standard concept.
- **`0` (in the `*_concept_id` column)** — "no translation found" = an unmapped record.
- **Review cycle** — find the unmapped codes, have a researcher decide the right translation, fill it in.
