# Harmony Forge — Model Card (pointer)

## Sealed test (Phase 16 Task 3)

- Location: `training/corpus/sealed_test.jsonl`
- Manifest: `training/corpus/sealed_manifest.json` (`sealed_sha256` pins the file)
- Rule: NEVER-OPENED — no eval, smoke, or baseline process may open the sealed
  path before the v2c single run (a later phase). A premature peek voids the seal.
- Split proofs: `training/tests/test_sealed.py` (IDs-only reads for
  piece/composer/melody disjointness; never scores).
- Status: NEEDS_CONTEXT — 41 sealed pieces (shortfall 19 vs 60); see manifest
  `cause`. Do not weaken the split to reach 60.
