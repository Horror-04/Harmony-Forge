"""Export the runtime §10 memo n-gram index (Phase 3 Task 3, item A).

Builds ``training/memo_index.bin`` from the SAME corpus + window definition
as the eval memo-ban filter (``training/evaluate.py`` + ``training/dataset.py``):

- source: ``training/corpus/train.jsonl`` ``ids`` vectors (TRAIN only — the
  same split the eval ``id_8`` set is built from);
- window: flat-id 8-grams, ``for k in range(max(0, len(ids) - 7))`` verbatim
  from ``dataset.py`` (no re-encoding, so the codec normalization — bar /
  subbeat / track-type / pitch / duration / velocity-bin, shared frozen
  layout of ``training/tokenizer.py`` and
  ``src/core/serialization/tokenizer.cpp`` — is identical by construction).

Format (little-endian, deterministic: n-grams sorted lexicographically)::

    offset  bytes  content
    0       4      magic b"HFMI"
    4       4      uint32 version (= 1)
    8       4      uint32 ngram count N
    12      32*N   N x 8 x int32 token ids, sorted

Size: ~518 ids vocab entries -> ~16.5k 8-grams -> ~0.5 MB (< 1 MB budget,
so the file is committed to ``training/`` next to the weights; the shipped
runtime loads the sibling ``memo_index.bin`` next to the configured model).

Determinism: pure function of ``training/corpus/train.jsonl`` (+ the
``--procedural``/``--seed`` that fixed that split); no randomness, sorted
output, fixed struct layout. The script cross-checks the built set against
``training/corpus/memo_ngrams.json::id_8`` and FAILS on mismatch (proof the
runtime index and the eval filter agree).

Run: ``python training/export_memo_index.py`` (stdlib only).
"""

from __future__ import annotations

import argparse
import json
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CORPUS_DIR = os.path.join(HERE, "corpus")
TRAIN_JSONL = os.path.join(CORPUS_DIR, "train.jsonl")
MEMO_JSON = os.path.join(CORPUS_DIR, "memo_ngrams.json")
OUT_BIN = os.path.join(HERE, "memo_index.bin")

MAGIC = b"HFMI"
VERSION = 1
WINDOW = 8  # same window as evaluate.py / dataset.py


def build_id8(train_path: str) -> set[tuple[int, ...]]:
    id_8: set[tuple[int, ...]] = set()
    with open(train_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            ids = json.loads(line)["ids"]
            # Verbatim window loop from training/dataset.py.
            for k in range(max(0, len(ids) - 7)):
                id_8.add(tuple(ids[k:k + 8]))
    return id_8


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=OUT_BIN)
    args = ap.parse_args()

    id_8 = build_id8(TRAIN_JSONL)

    with open(MEMO_JSON) as f:
        memo = json.load(f)
    memo_id8 = set(map(tuple, memo["id_8"]))
    if id_8 != memo_id8:
        only_local = len(id_8 - memo_id8)
        only_memo = len(memo_id8 - id_8)
        print(f"MISMATCH vs memo_ngrams.json::id_8 "
              f"(only-export={only_local} only-memo={only_memo}); "
              f"runtime index and eval filter DISAGREE — refusing to write.",
              file=sys.stderr)
        return 1

    ordered = sorted(id_8)
    with open(args.out, "wb") as f:
        f.write(MAGIC)
        f.write(struct.pack("<I", VERSION))
        f.write(struct.pack("<I", len(ordered)))
        for w in ordered:
            f.write(struct.pack("<8i", *w))
    size = os.path.getsize(args.out)
    print(f"memo_index: ngrams={len(ordered)} bytes={size} "
          f"({size / 1048576:.2f} MB) matches memo_ngrams.json::id_8 "
          f"-> {os.path.basename(args.out)}")
    if size >= 1048576:
        print("OVERSIZE: index >= 1 MB budget — do not commit as-is.",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
