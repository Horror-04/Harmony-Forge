# Locked-43 looks log (append-only)

> **Counter mechanism (binding from 2026-10-16, gate-v3 amendment):**
> every future scoring run that touches `locked-43` / `test_locked-43`
> (model, baseline, or probe — full or partial) appends one row to the
> table below BEFORE running (date, purpose, config, planned units,
> performer), and fills `actual` + `artifact` after. No row = the run did
> not happen. `docs/METRICS.md` holds the running counter; this file is
> the itemized log. History before this mechanism is backfilled below
> from committed artifacts only — local/uncommitted looks from that era
> are uncounted (see floor note).

## Backfill (reconstructed 2026-10-16 from committed eval/AB JSONs)

Floor note (honest, no false precision): the second-opinion review found
20+ looks went uncounted in the pre-log era. Reconstruction below accounts
**27 committed scoring runs** (every committed artifact that embodies a
fresh full pass over locked-43/test_locked-43 gets a row). Unlogged local
looks on top of that — blind A/B audio renders, listening passes,
exploratory rescores — cannot be reconstructed and stay uncounted. The
"20+" was a floor then; reconstruction (27) is consistent with it, and the
accountable past total is now **27+ (27 committed + uncounted locals)**.
Locked-43 is dev from here (see `docs/METRICS.md` dev-declaration); the
forward counter starts at past = 27+.

Counts below are RUNS (fresh passes over locked prefixes), not scores —
no score numbers are restated here (they live in the artifacts).

| # | artifact (committed) | phase | runs | units | config gist |
|---|---|---|---|---|---|
| 1 | `training/eval_v2_s{7,11,23,42,99}.json` | 9 | 5 | 5×43 | greedy, 5 seeds |
| 2 | `training/eval_v2b_s{7,11,23,42,99}.json` | 11 | 5 | 5×43 | greedy, 5 seeds |
| 3 | `training/eval_test_locked_v1ref.json` | 9 prep | 1 | 43 | v1-greedy reference |
| 4 | `training/baseline_scores_test_locked.json` | 9 prep | 2 | 2×43 | kn + theory arms (v1_greedy entry is a re-used reference, NOT a look) |
| 5 | `tools/task4_metrics.json` | 10 | 4 | 4×43 test_locked (+4×33 val, not locked) | greedy / sampler-T1.0 / sampler-T0.85 / theory-only |
| 6 | `tools/task12_metrics.json` | 12 | 6 | V0 43, V1–V5 5×86, V6 43 | V0–V6 grid; V2/V5 dual labels = ONE run (identical Cfg by construction), 7 cells from 6 runs |
| 7 | `tools/task13_metrics.json` | 13 | 4 | K0/K1/K3 3×86, K2 43 | K0 = V1-config re-run control, K1/K2/K3 keynorm arms |
| — | `tools/interval_memo_report.json` | 14 | 0 full runs | derived pools (detection 10 + survival 54 + FP 4 + full-val 33 context) | probe on locked-derived pools + K0 repro check; no fresh full pass, listed for completeness |
| — | `training/decode_ab.json` | 9 | 0 (val-33, not locked) | — | 8-config sampler sweep on val; listed to prevent miscounting |
| — | `training/eval_v2_rescore.json`, `eval_v2val_*`, `eval_report.json` | 8–9 | 0 (val-33, not locked) | — | val-split history; not locked looks |

Committed-run total: **27**. Unlogged locals: uncounted (floor applies).

## Forward log (append rows BEFORE running)

| date | purpose | config | planned units | performer | actual | artifact |
|---|---|---|---|---|---|---|
| 2026-10-16 | Phase-15 Task-2 evidence run (one-split table + oracle + DF-audit + canonical; Task-3 verdict input, MEASURE ONLY) | WIRED_CFG verbatim (T=1.0/top_p=1.0/memo-2/strict+fsm/lam=0); frozen scorer; cells v1_sampler/v2b_sampler/theory/rand_theory/kn_raw/kn_stack + oracle(true halves, scores-only) + K1 regen (DF/canonical source); seeds {7,11}, RNG seed*1000+idx | 559 locked units: v1 86, v2b 86, theory 43, randtheory 86, knraw 43, knstack 86, k1regen 86, oracle 43 (NLL on val-composed is NOT locked: 0) | task-2 worker (CPU) | 559/559, wall 27s, box_hit=False, K0repro OK, K1repro OK | tools/step1_table.json |
| 2026-10-16 | Phase-17 Task-3 causal cells (torch greedy, NO memo filter, halved prefixes; engine-fresh-new-seed prompts + locked-43 dev; 5 arms x 5 folds short-schedule small-arch; control e974390d) | CTRL fixed-bank / A stream / B cap10+es2-2 / C fsm-mask / D k2+crop; folds 18/14/15/15/17 (J+P merged); gen budget 48 | 3200 engine-fresh-new units (25 cells x 128) + 1075 locked dev units (25 cells x 43); NLL on 79 fold-held (NOT locked: 0) | task-3 worker (GPU) | PENDING | training/causal_results.json |
