# Phase 16 Implementation Plan (automated licensed data scale + sealed test)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Scale licensed-clean composed data by automation (target ≥10M tokens, stretch 30M) with per-file license manifests, then freeze a sealed composed test (≥60 pieces, split by piece+composer, hash committed, single-opening discipline) — the fuel and the exam for the v2c single run (Phase 17, NOT this phase).

**Architecture:** Manual intake (Phases 9/11: 86 records) cannot reach 10M tokens — automation must. Pipeline: source survey (Mutopia full PD catalog, OpenScore full CC0 catalog, PDMX-class MuseScore metadata corpora — each with per-source license boxes) → per-file fetch + license gate (PD-composition ≠ PD-encoding enforced per FILE; arrangement-of-others'-songs refused; PDMX file-labels distrusted without composition-rights evidence) → SATB/homophonic reduction via the shared `score_to_satb` (reuse, no fork) → near-dup MinHash across ALL sources + existing corpus → style filters (homophonic 4-voice, chorale/lieder/quartet idiom) → volume counts. Then sealed test carved by piece+composer from the fresh pool (never train, never val, never opened until v2c). v2c training itself is Phase 17.

**Tech Stack:** Python 3.14 stdlib + repo `training/ingest/*` (reuse ledger/dedupe/reduction), CPU. No GPU, no training, no C++.

**Spec:** `docs/SPEC.md` (§10 licence-clean), `training/MODEL_CARD.md`, phase-15 gate v3 (sealed-split-deferred clause + trigger — THIS phase executes the deferred part unconditionally per the GO work order, since scale without a sealed exam is unverifiable).

## Global Constraints

- LICENSE-FIRST, now at scale (hard gate): per-FILE evidence (source/url/license/sha + quoted header/license-file lines for batches); PD-composition ≠ PD-encoding per file; arrangements of copyrighted songs refused even with PD file labels (PDMX warning); SA/NC/unknown → refuse; ToS-respecting fetch (rate limits, small concurrent footprint); ≤30 min license box PER SOURCE (not per file — batch evidence + spot audits).
- Sealed discipline: sealed test committed + hashed; NO scoring of any candidate on it in this phase (not even baselines — first opening is the v2c single run; a premature peek disqualifies the seal — state it in the file header).
- No weights/retraining/scorer/gate/C++ changes. Absolute pitches (keynorm downstream). Record shape = dataset.py + meta (as before). Forbidden paths uncommitted. PowerShell, no bash.

## Review Focus

- Scale laundering (bulk accept on project-level license without per-file evidence) — expected per-file rows + spot-audit protocol with refusal examples, not just accepts.
- Near-dupes across sources (same chorale in Mutopia + OpenScore + CPDL) counted twice — expected cross-source MinHash with dedupe counts per pair.
- Style drift (virtuoso solos, orchestral reductions counted as chorale idiom) — expected filter precision sample (manual audit N=30 with verdicts).
- Sealed test contaminated (piece/composer overlap with train, or opened early) — expected group-split proof + hash + never-opened attestation.
- Volume vanity (token count inflated by procedural/duplicates) — expected composed-only token accounting with dedupe applied.

---

### Task 1: Source survey + manifest pipeline (boxes)

**Files:**
- Create: `training/ingest/auto_manifest.py` (source registry + per-file evidence rows + spot-audit sampler), `training/tests/test_auto_manifest.py`
- Modify: `training/corpus/sources.csv` (new source rows, evidence-led)

**Interfaces:**
- Consumes: `ledger.py` (allowlist + validate), existing source verdicts (JSB-refused, Mutopia-PD, OpenScore-CC0).
- Produces: approved-source list + evidence format for Task 2.

- [ ] **Step 1: Survey boxes** (Mutopia-full, OpenScore-full, PDMX-class — ≤30 min license box each; verdict per source: APPROVED/REFUSED + evidence) — record first.

- [ ] **Step 2: Failing tests** (manifest row validation, refusal paths, spot-audit sampler).

- [ ] **Step 3: Implement pipeline + commit** (registry + tests + source rows; zero intake records yet).

**DoD:** approved sources with evidence; pipeline GREEN; no records (intake is Task 2).

### Task 2: Bulk intake + near-dup + style filters (volume)

**Files:**
- Create: `training/ingest/bulk_run.py` (fetch → gate → reduce → dedupe → filter → ledger)
- Modify: corpus intake files + `sources.csv` (counts), listening skeleton (verdict enum, sample only)

**Interfaces:**
- Consumes: Task-1 pipeline + approved sources; `score_to_satb` shared reduction; `dedupe.py` + cross-source MinHash (new, tested); style filter (homophonic 4-voice + idiom).
- Produces: volume corpus + counts for Task 3.

- [ ] **Step 1: Failing tests** (cross-source dup caught; style filter accepts/rejects crafted; ledger real shas).

- [ ] **Step 2: Boxed bulk runs per source** (ToS-respecting; stop per-source on box end, report yields) + near-dup report + style audit N=30 + commit.

**DoD:** composed-token counts (post-dedupe) + audit; target ≥10M tokens or honest shortfall with cause.

### Task 3: Sealed test ≥60 pieces (hash, single opening)

**Files:**
- Create: `training/corpus/sealed_test.jsonl` + `sealed_manifest.json` (ids, pieces, composers, sha256 of file, NEVER-OPENED header)
- Test: `training/tests/test_sealed.py` (group-split proof vs train/val/intake by piece AND composer AND melody; hash matches manifest)

**Interfaces:**
- Consumes: Task-2 pool (carve only, no training use); dedupe/group-split machinery.
- Produces: the exam for Phase-17 v2c (unopened).

- [ ] **Step 1: Failing tests** (split proofs, hash match, never-opened header present).

- [ ] **Step 2: Carve + prove + commit** (≥60 pieces; hash in manifest + MODEL_CARD pointer; NO scoring run on it — not even a smoke eval).

**DoD:** sealed file + passing split proofs + zero openings (attested in manifest).

## Self-Review

- **Spec coverage:** §10 (licence per-file + arrangement rule + ToS) → T1/T2; honesty (sealed discipline) → T3; no §8/§11 touch. Gaps: v2c run (Phase 17 by design).
- **Step scan:** each step one action + Expected; no bodies.
- **Type consistency:** `auto_manifest.py`, `bulk_run.py`, `sealed_test.jsonl`, `sealed_manifest.json` — new names; reused shapes unchanged.
- **Review Focus:** 5 lines owned (laundering → spot-audits; cross-dups → MinHash pairs; drift → N=30 audit; contamination → split proofs; vanity → post-dedupe accounting).
- **Proportion:** 3 tasks, no bodies.
