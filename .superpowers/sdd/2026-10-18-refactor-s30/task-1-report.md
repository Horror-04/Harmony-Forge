# Task 1 report (S3.0 Phase 1) — legs×stages + Arrange-UI + stage order + CCN

Branch `refactor/s3-0`, base a80ce72. Phase 2 (corruptions) NOT touched.

## A. Legs × stages → `docs/measurements/s3-0-legs-stages.md`

- Method: 9 scratch `stderr` counters (additive-only: 11 insertions, 0
  deletions), `build-off` Debug, 256 `render_midi` runs (8 corners ×
  seeds 0–31, rc=0 all) + 6 test binaries + 1 `--arrange` cell.
- Headline: **NO cube leg reaches the C++ sampler call-site**
  (`S30_SAMP_SITE=0`, `S30_SAMP_ENTER=0` in all 8 corners × 32 seeds).
  Every MIDI leg: `IMPL=32, MODE=128, GREEDY_EMPTY=128` per corner;
  keynorm hook fires only on ON corners (128/128, net no-op under the
  empty model path); sampling-ON corners enter the wrapper (128) but
  fall back to greedy before `:497` (provider unavailable, empty
  `model_path`). `GREEDY_PATH=0` everywhere (no cube leg sets a model
  path). `render_model` legs (incl. v2b): zero C++ stages by
  construction (pure-Python file; import/subprocess grep) + step-5
  37/37 replication as the per-leg path evidence.
- Guard per stage named (test names + 128 output-sha set with its
  proven track-5 blindness, step-5 §5 item 3).
- Unit-test counts: candidates 16/64/0/0/0/0/64/0; sampler
  28/112/0/0/48/**0**/93/48/64 (`ENTER=93` direct-stub calls prove the
  counter live; `SITE=0` = `:497` is build-full-only via the wiring
  flag-ON test); keynorm 6/24/8/8/0/0/4/20; ort_logits + tokenizer all
  zero; memo_e2e build-off stub zero (real e2e build-full-only, not run
  per build-full ban — mapped by code reading).
- No result contradicted E2's mechanism; everything confirmed it
  (composer emits tracks 0/1/2 only; Python decode moves model legs).

## B. Arrange-UI → `docs/measurements/s3-0-arrange-ui.md`

One paragraph: UI has no mode control (ArrangeBar.h editors only),
`Section`/SPEC carry no mode, Strict forced twice
(`PatternDocument.cpp:94`, `arrangement.cpp:244`). Verdict: no dead
control, no cleanup item; Creative-arrange = Phase-B feature, not a fix.

## C. Stage order → `docs/measurements/s3-0-stage-order.md` (committed 172949b)

Line-by-line table on current code: per-candidate stages 0–9 with
file:line, input→output, RNG per stage (per-index `mt19937` shared by
ref for compose/transform/mode; per-call integer Pcg32 seeded
`p.seed+i` for the sampler; hash draws at arrangement level; no RNG in
caps/memo). Norm/denorm sites (`:544/:569` → `keynorm.cpp:117/136`;
flat-codec `keynorm.cpp:67/93` test-only, zero src/ callers). THE single
sampler call-site `:497` (only `sample_continue(` call in src/ outside
its definition). constraints.cpp overlap recorded: `apply_mode:363`
calls it; sampler re-implements on shared predicates (no second table).

## D. CCN → `docs/measurements/s3-0-ccn.md`

lizard 1.24.1, S0 method reproduced exactly (constraints.cpp row
reproduced cell-for-cell; acef4de-vs-current candidates diff = one
commit, function CCNs unchanged). Aggregate
`candidates.cpp,25,441,30,6.24,4,3`. Exceptions (>15):
`compose_base` :118-174 CCN 16, `apply_candidate_transform` :228-306
CCN 30, `apply_mode` :311-364 CCN 30.

## Revert proof

`git checkout --` the 3 counter files → `git status` = 3 pre-existing
untracked dirs only; `git diff` and `git diff -- src/` both empty.
Counter binaries rebuilt pristine (build-off Debug; build dirs
git-ignored). Scratch drivers in `$env:TEMP\s30ctr\`, deleted.

## Self-review

- Decision (1) honored: final tree zero `src/` delta (proof above).
- (2a): all counts summed over 32 seeds, uniform per seed (128=4×32, no
  seed skipped a stage); guard test named per stage incl. the 128
  output-sha set + boundary-blindness citation.
- (2b): one paragraph + backlog verdict, nothing fixed.
- (2c): done first (committed 172949b before counters ran); file:line
  per stage, RNG types, norm/denorm sites, single call-site,
  constraints overlap recorded-not-touched.
- (2.5): CCN by s0-lizard.csv method (reproduction proven two ways).
- (2.6): only `cmake --build build-off --config Debug` on 7 targets;
  no build-full; load 37%, default parallelism, no throttle needed.
- Track-5 conditional did NOT trigger (no mock-model sampler fixture
  was built — build-off stub provider can't engage it; building one
  would have needed build-full). Standing evidence cited (step-5 §5.3).
- I twice dropped a source line with sloppy `edit` newStrings and
  repaired both immediately; final counter diff verified purely
  additive before building, and post-revert diff is empty — no residue.

## Concerns

1. `:497` reachability has NO build-off guard by construction (stub
   provider) — the only guards are build-full (wiring flag-ON test +
   dump_worker_ids 128-set). If S3 refactors the call-site, a
   build-full proof run is mandatory.
2. Creative/Experimental mode arms have no dedicated output-shape unit
   test (only determinism+caps + the 512 banked C-ok byte pins) — a
   mode-body break that preserves determinism would pass unit tests and
   only redden the cube.
3. `s0-lizard.csv` `nloc_total` = sum of per-function NLOC (not the
   file-level Total nloc) — verified twice; future ratchet tooling must
   use the same aggregation.
