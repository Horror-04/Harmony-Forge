"""Golden-vector parity: Python tokenizer output must equal fixtures.

Run: ``python training/tests/test_parity.py`` (stdlib only, exit 0 = PASS).
The C++ side (``tests/test_tokenizer.cpp``) embeds the same numbers and
asserts decode/encode equality — no JSON parser in C++ by design (R3).
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import tokenizer as tok

VECTORS_PATH = os.path.join(os.path.dirname(__file__), "..", "parity_vectors.json")


def main() -> int:
    with open(VECTORS_PATH) as f:
        doc = json.load(f)
    vectors = doc["vectors"]
    assert vectors, "no parity vectors"
    for v in vectors:
        name, pattern, ids = v["name"], v["pattern"], v["ids"]
        got = tok.encode_pattern(pattern)
        assert got == ids, f"{name}: encode mismatch\n got={got}\n exp={ids}"
        back = tok.decode_tokens(ids)
        assert back is not None, f"{name}: decode returned None"
        assert tok.encode_pattern(back) == ids, f"{name}: roundtrip mismatch"
        print(f"PASS {name}: {ids[0]} notes, {len(ids)} tokens")
    print(f"ALL {len(vectors)} parity vectors PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
