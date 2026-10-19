# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""S10.1 off-golden literal census (BLOCKING gate, stdlib only).

Counts, per file, for ``tests/*.cpp`` and ``training/tests/*.py``, the
magic-number classes that an S4b-main fixture migration would have to move
into golden files:

  (a) digest: 64-hex literals + any other hex run >= 16 chars;
  (b) vector: brace/bracket regions holding >= 4 numeric literals;
  (c) assert-numeric: REQUIRE/CHECK/assert/check( lines with an integer
      literal >= 1000 (auto heuristic) + MANUAL parity-test list below;
  (d) tolerance: approx-family identifiers or float literals on assert lines.
  (e) string-table: initializer-like {} (cpp) / [] (py) regions holding
      >= 3 quoted-string literals (quote-aware raw scan, exact lines).

Registered in-test goldens (``tests/golden_manifest.json`` ``in_test``) and
genuine test parameters (seeds, counts, indices: literals that PARAMETERIZE a
test rather than pin a value) are a SEPARATE non-violation category
(``registered`` / ``parameter``) carved out WITH a stated reason (the same
allowlist-with-reason mechanism as ``tools/score_sheet.md``).
S10.1 — this lint is BLOCKING (it exits non-zero on a violation): HARD-ZERO
``digest64``/``hex16+`` must be 0 (they are 0 today); the per-file counts of
vectors/strings/assert>=1000/toler and the TOTAL may not GROW (a total-only
ratchet lets literals be MOVED between files — the owner's reason). The pins
and the classification blocks live in ``tools/off_golden_ratchet.py`` (next
to this script); the MANUAL_PARITY map below carries its own classification
next to each of its 15 entries.

Usage: py -3 tools/lint_off_golden.py [--root DIR]
Exit 0 = PASS, 1 = FAIL. Read-only. String tables (e) share the vector block
shape and carve-outs; a block may count in both (b) and (e) with disjoint
elems (no literal is counted twice; short pin strings never reach the floor).
"""

from __future__ import annotations

import argparse
import glob
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import off_golden_ratchet as RATCHET  # noqa: E402  (companion data module)

# ---------------------------------------------------------------------------
# Manual parity-test list (read, not guessed: each entry was verified by
# reading the test source; result rows carry auto/manual marks).
# class: registered (a manifest in_test entry) | parity-file (mirrors a
#   checked-in golden/fixture file) | relational (two live code paths) |
#   echo (the test writes the values then reads them back) | parameter
#   (seeds/counts/indices/thresholds that parameterize, not pin) | golden
#   (UNREGISTERED run-captured pin: the S4b-main migration scope).
# The 5th element is the S10.1 classification of the entry (one line each):
#   мигрирован = anchored by a file-backed pin/registry; структурный =
#   stays in the test source (a parameter, an echo, a relational comparison
#   or a pending-migration capture) — the reason says why it cannot move;
#   allowlist = the census ALLOWLIST exempts it (the reason cites the rule).
# One PHYSICAL line each on purpose: this tool must stay under the 500-line
# file-size gate (tools/lint_file_size.py).
# ---------------------------------------------------------------------------
MANUAL_PARITY = [
    # tests/*.cpp
    ("tests/test_s4b_mode_shape.cpp",
     "s4b Creative/Experimental shape goldens G1/G2/G3", "registered",
     "manifest in_test 1-3 (kTones/kFlips/kKept + seed 7); structural CHECKs are not goldens",
     "мигрирован — the G1/G2/G3 shape goldens are registered in tests/golden_manifest.json (in_test records 6-8): the values are file-backed by the manifest registry"),
    ("tests/test_s4b_seed_binding.cpp",
     "s4b sampler index-seed binding kPinned[3][4]", "registered",
     "manifest in_test 4 (seeds 0/10/11 per-index FNV hashes)",
     "мигрирован — the kPinned[3][4] hash table is registered in tests/golden_manifest.json (in_test record 9): file-backed by the manifest registry"),
    ("tests/test_sampler.cpp",
     "wiring flag OFF kPinned[3][4] (pre-phase history bytes)", "golden",
     "UNREGISTERED run-captured pin: 12 hex digests, needs registration or migration",
     "структурный — UNREGISTERED run-captured pin (12 hex digests): migratable, but only under the S4b-main migration scope; held in-test and NOT allowlisted, so the census still counts it (ratchet: must not grow)"),
    ("tests/test_tokenizer.cpp",
     "7 golden: cases mirroring training/parity_vectors.json", "parity-file",
     "vectors embedded verbatim (R3: no JSON lib in C++); migrate WITH the json file",
     "мигрирован — the vectors mirror training/parity_vectors.json (file-backed): the C++ copy must move WITH that file, it is not a new pin"),
    ("tests/test_keynorm.cpp",
     "python parity vectors byte-identical (+echo round-trips)", "parity-file",
     "ids/want vectors produced by training/keynorm.py; relational to_canonical/from_canonical",
     "мигрирован — the vectors mirror the file-backed parity set (tests/golden/keynorm_vectors.json, registered as in_test 0-1): the C++ copy is a verbatim mirror"),
    ("tests/test_slot_bitmap.cpp",
     "frozen slot bitmap exhaustive (reads tests/golden/slot_bitmap.txt)", "parity-file",
     "zero in-test literals: golden-file pattern already, probe vector is fixture",
     "мигрирован — the frozen slot bitmap is a file-backed golden (tests/golden/slot_bitmap.txt, frozen pin d66faabf, tools/lint_golden_pin.py): the probe row is its stimulus"),
    ("tests/test_chordtrack_pin.cpp",
     "ChordTrack statics pre-edit capture (28 string rows)", "golden",
     "UNREGISTERED string-literal pin (category (e) string-table: counted class)",
     "структурный — UNREGISTERED string-literal pin (28 rows): migratable only under the S4b-main migration scope; held in-test, NOT allowlisted, so the census still counts it"),
    ("tests/test_s30_sampler_seed.cpp",
     "ENTER seed-sensitivity (property, seeds 42/7/8) + Task-2 Pcg32 pin "
     "(two-instance stream determinism, r7/r42 reference draws, unit [0,1))",
     "relational",
     "determinism + sensitivity inequalities only; reference draws are pure "
     "uint64 arithmetic (stdlib-independent by construction, not run-captured "
     "pins); 1000/100/200 are draw-count parameters, 0.0/1.0 unit-range bounds",
     "allowlist — the census ALLOWLIST exempts the LCG-stub constants, the determinism property and the unit() range bounds (parameter class): they parameterize, they do not pin"),
    # training/tests/*.py
    ("training/tests/test_parity.py",
     "tokenizer parity vs parity_vectors.json", "parity-file",
     "reads the golden file; no in-test literals",
     "мигрирован — reads the file-backed golden (training/parity_vectors.json); the test itself carries no literals"),
    ("training/tests/test_sealed.py",
     "sealed-test split proofs vs corpus + manifest", "relational",
     "manifest cross-checks; 60 is a count policy threshold (parameter)",
     "структурный — the 60 is a count-policy threshold (a parameter of the split contract) and the manifest cross-check is relational: neither is a captured value that could be migrated"),
    ("training/tests/test_ckpt.py",
     "save/progress round-trips (2.3456, (2,12) self-echo)", "echo",
     "test writes the values then reads them back; seeds/counts are parameters",
     "структурный — self-echo: the test writes the values (2.3456, (2,12)) and reads them back: there is nothing to migrate"),
    ("training/tests/test_decode.py",
     "memo-run equivalence vs evaluate oracle; T=0.01 argmax property", "relational",
     "got==exp compares two live paths; 33 pins a frozen corpus count (file-backed)",
     "структурный — relational: got==exp compares two live paths; the 33 is a frozen corpus count that is already file-backed (the corpus): no in-test capture to migrate"),
    ("training/tests/test_causal_ab.py",
     "gate-accepts-pin via assert_config_pinned", "relational",
     "config-pin helper comparison, not a value capture",
     "структурный — relational: the gate-accepts-pin helper compares two live values: no captured output to migrate"),
    ("training/tests/test_slot_range_unified.py",
     "d66faabf frozen-pin reference", "parameter",
     "references the frozen bitmap pin (lint_golden_pin.py domain), pins nothing new",
     "allowlist — the census ALLOWLIST exempts the frozen-bitmap pin reference (lint_golden_pin.py domain): it references the pin, it pins nothing new"),
    ("training/tests/test_tokenizer_spec_read.py",
     "d66faabf frozen-pin reference", "parameter",
     "references the frozen bitmap pin, pins nothing new",
     "allowlist — the census ALLOWLIST exempts the frozen-bitmap pin reference (lint_golden_pin.py domain): it references the pin, it pins nothing new"),
]

# Allowlist with reason: (file basename, regex, category, reason).
# Registered regions: (file basename, start-line regex, end-line regex,
# category, reason). The identifier (kPinned, ...) sits outside the literal
# lines, so line-local allowlists cannot carve them.
REGISTERED_REGIONS = [
    ("test_s4b_seed_binding.cpp", r"kPinned\[3\]\[4\]",
     r"^\s*\};", "registered", "manifest in_test 4 kPinned table"),
]

ALLOWLIST = [
    ("test_s4b_mode_shape.cpp", r"kTones|kFlips|kKept|kTargets",
     "registered", "manifest in_test 1-3 exact lists"),
    ("test_s4b_mode_shape.cpp", r"std::mt19937 rng(_s)?\(777\)|std::mt19937 rng\(7\)",
     "registered", "manifest: G1 rng-free (777 determinism anchor), G2 seed 7 pinned in-test"),
    ("test_s4b_seed_binding.cpp", r"kPinned|kSeeds|1469598103934665603|1099511628211",
     "registered", "manifest in_test 4 (hashes + FNV helper constants)"),
    ("test_s4b_seed_binding.cpp", r"0123456789abcdef",
     "parameter", "hex-digit lookup table (hash machinery, not a pinned value)"),
    ("test_sampler.cpp", r"1469598103934665603|1099511628211",
     "parameter", "FNV-1a helper constants (hash machinery, not pinned values)"),
    ("test_sampler.cpp", r"0123456789abcdef",
     "parameter", "hex-digit lookup table (hash machinery, not a pinned value)"),
    ("test_causal_ab.py", r"0123456789abcdef",
     "parameter", "hex-charset membership check (format assertion, not a pinned value)"),
    ("test_s30_sampler_seed.cpp", r"6364136223846793005|1442695040888963407",
     "parameter", "LCG stub constants mirroring the sampler test double"),
    ("test_sampler.cpp", r"6364136223846793005|1442695040888963407",
     "parameter", "LCG stub constants mirroring the sampler test double"),
    ("test_slot_range_unified.py", r"d66faabf.*7854f58",
     "parameter", "frozen bitmap pin reference (lint_golden_pin.py domain)"),
    ("test_tokenizer_spec_read.py", r"d66faabf.*7854f58",
     "parameter", "frozen bitmap pin reference (lint_golden_pin.py domain)"),
    ("test_model_manifest.cpp", r"e3b0c44298fc1c14|ba7816bf8f01cfea",
     "parameter", "FIPS 180-4 standard vectors (empty and abc): spec-published "
     "self-test of the sha256 implementation, not run-captured pins"),
    ("test_s30_sampler_seed.cpp", r"a\.next\(\) == b\.next\(\)",
     "parameter", "Pcg32 stream determinism property: two live instances "
     "compared (relational); 1000 is the draw-count parameter, not a pin"),
    ("test_s30_sampler_seed.cpp", r"v >= 0\.0|v < 1\.0",
     "parameter", "unit() range property bounds [0,1): definitional, not "
     "captured pins"),
    ("test_preview_scheduler.cpp", r"mel\.notes = \{\{",
     "parameter", "audition-pattern Note inputs (scheduler stimulus: pitches/"
     "starts/durs/vels parameterize the drain; pinned outputs are the "
     "sub-floor timeMs CHECKs)"),
    ("test_preview_scheduler.cpp", r"bass\.notes = \{\{",
     "parameter", "single-note bass input fixture for the non-empty-preference "
     "path (direct-track stimulus; expected 0/500 timeMs are sub-floor)"),
    ("test_preview_scheduler.cpp", r"kT0 \+ 99999",
     "parameter", "far-future nowMs offset for the terminal-idle empty-queue "
     "property (time parameter, not a pinned value)"),
]

ASSERT_RE = re.compile(r"REQUIRE|CHECK|assert|check\s*\(")
HEX64_RE = re.compile(r"[0-9a-fA-F]{64}")
HEX16_RE = re.compile(r"[0-9a-fA-F]{16,}")
INT_RE = re.compile(r"(?<![\w.])(0x[0-9a-fA-F]+|\d[\d_]*)(?![\w.])")
FLOAT_RE = re.compile(r"(?<![\w.])\d+\.\d+")
TOL_RE = re.compile(r"Approx|WithinAbs|WithinRel|[Ee]psilon|[Mm]argin|approx|allclose|isclose|abs_tol|rel_tol")


def _nl(m):
    return "\n" * m.group(0).count("\n")


def strip_css(text):
    text = re.sub(r"/\*.*?\*/", _nl, text, flags=re.S)
    text = re.sub(r"//[^\n]*", " ", text)
    text = re.sub(r'"(?:[^"\\]|\\.)*"', '"S"', text)
    text = re.sub(r"'(?:[^'\\]|\\.)*'", "'C'", text)
    return text


def strip_py(text):
    text = re.sub(r'"""[\s\S]*?"""', _nl, text)
    text = re.sub(r"'''(?s:.)*?'''", _nl, text)
    text = re.sub(r"#[^\n]*", " ", text)
    text = re.sub(r'"(?:[^"\\]|\\.)*"', '"S"', text)
    text = re.sub(r"'(?:[^'\\]|\\.)*'", "'C'", text)
    return text


def allowed(path, snippet, category):
    base = os.path.basename(path)
    for f, rx, cat, _reason in ALLOWLIST:
        if f == base and cat == category and re.search(rx, snippet):
            return True
    return False


def in_registered_region(path, lineno, raw_lines):
    base = os.path.basename(path)
    for f, start_rx, end_rx, _cat, _reason in REGISTERED_REGIONS:
        if f != base:
            continue
        s = None
        for i in range(lineno, 0, -1):
            if re.search(start_rx, raw_lines[i - 1]):
                s = i
                break
            if re.search(end_rx, raw_lines[i - 1]):
                break
        if s is None:
            continue
        for i in range(lineno - 1, min(len(raw_lines), lineno + 40)):
            if re.search(end_rx, raw_lines[i]):
                return True
        return True
    return False


def _str_tables(path, raw_lines):
    # Category (e): initializer-like {} (cpp) / [] (py) regions holding
    # >= 3 quoted-string literals. Same region shape as (b) (init-like test,
    # outermost fold, registered carve-out on the start-line context) but
    # scanned on the RAW lines with a quote/comment-aware walker, NOT the
    # masked stream: the (a)-(d) maskers can glue lines together when a quote
    # opens inside the other quote kind (training/tests/test_sealed.py masks
    # 180 raw lines to 163; test_ingest.py 541 to 538), which misattributes
    # block lines. String counting needs exact lines — and must not see
    # brackets inside strings — so (e) tracks code/string/comment modes and
    # counts each closing quote as one literal for every open frame (nested
    # inits fold outward, as in (b)). Floor >= 3: TEST_CASE name+tag pairs
    # are 2 wide and excluded as non-init bodies anyway; 3 keeps
    # single/double string inits out while firing on real tables. Numeric
    # and string elems are disjoint classes, so a mixed block (chordtrack
    # rows) counts in both (b) and (e) without double-counting any literal.
    # No R"( raw strings exist in scope (checked); a future one needs a
    # raw-string mode here.
    is_py = path.endswith(".py")
    opens, closes = ("[", "]") if is_py else ("{", "}")
    notre = re.compile(r"^\s*(namespace|struct|class|enum)\b")
    blocks = []
    stack = []  # [start_line, is_init, strings, parent_is_init]
    prev_sig = ""  # significant code chars before the opener
    mode = "code"  # code | block | sq | dq | tsq | tdq
    for i, ln in enumerate(raw_lines, 1):
        j = 0
        while j < len(ln):
            ch = ln[j]
            nx = ln[j + 1] if j + 1 < len(ln) else ""
            if mode == "code":
                if is_py and ch == "#":
                    break
                if not is_py and ch == "/" and nx == "/":
                    break
                if not is_py and ch == "/" and nx == "*":
                    mode = "block"
                    j += 2
                    continue
                if is_py and ch == nx == '"' and ln[j + 2:j + 3] == '"':
                    mode = "tdq"
                    j += 3
                    continue
                if is_py and ch == nx == "'" and ln[j + 2:j + 3] == "'":
                    mode = "tsq"
                    j += 3
                    continue
                if ch == '"':
                    mode = "dq"
                elif ch == "'":
                    mode = "sq"
                elif ch == opens:
                    is_init = True
                    if prev_sig.endswith(")") or prev_sig.endswith("else"):
                        is_init = False
                    if notre.search(ln):
                        is_init = False
                    parent_init = any(fr[1] for fr in stack)
                    stack.append([i, is_init, 0, parent_init])
                    prev_sig = ""
                elif ch == closes and stack:
                    s, is_init, ns, parent_init = stack.pop()
                    if is_init and not parent_init:
                        ctx = raw_lines[s - 1] + " " + (
                            raw_lines[s - 2] if s >= 2 else "")
                        if ns >= 3 and not allowed(path, ctx, "registered"):
                            blocks.append((s, i, ns,
                                           raw_lines[s - 1].strip()[:80]))
                else:
                    if ch.strip():
                        prev_sig += ch
            elif mode == "block":
                if ch == "*" and nx == "/":
                    mode = "code"
                    j += 2
                    continue
            elif mode in ("sq", "dq"):
                q = "'" if mode == "sq" else '"'
                if ch == "\\":
                    j += 2
                    continue
                if ch == q:
                    mode = "code"
                    for fr in stack:
                        fr[2] += 1
            else:  # tsq | tdq: triple-quoted spans lines; brackets inside
                q = "'''" if mode == "tsq" else '"""'
                if ln[j:j + 3] == q:
                    mode = "code"
                    for fr in stack:
                        fr[2] += 1
                    j += 3
                    continue
            j += 1
        prev_sig = prev_sig[-24:]
    return blocks


def census_file(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        raw = f.read()
    raw_lines = raw.split("\n")
    # Hex runs live in string literals: scan the comment-stripped text with
    # strings INTACT (string contents are masked only for the other classes).
    hex_src = re.sub(r"/\*.*?\*/", " ", raw, flags=re.S)
    hex_src = re.sub(r"//[^\n]*", " ", hex_src)
    hex_src = re.sub(r"#[^\n]*", " ", hex_src)
    code = strip_py(raw) if path.endswith(".py") else strip_css(raw)
    lines = code.split("\n")
    hex_lines = hex_src.split("\n")
    out = {"digest64": [], "hex16": [], "vectors": 0, "vec_elems": 0,
           "vec_blocks": [], "strings": 0, "str_elems": 0, "str_blocks": [],
           "assert_num": [], "toler": []}
    for i, ln in enumerate(lines, 1):
        hln = hex_lines[i - 1] if i - 1 < len(hex_lines) else ""
        for m in HEX64_RE.finditer(hln):
            if in_registered_region(path, i, raw_lines):
                continue
            if not allowed(path, hln, "registered") and not allowed(path, hln, "parameter"):
                out["digest64"].append((i, m.group(0)[:16] + "..."))
        for m in HEX16_RE.finditer(hln):
            if len(m.group(0)) == 64:
                continue
            if in_registered_region(path, i, raw_lines):
                continue
            if not allowed(path, hln, "registered") and not allowed(path, hln, "parameter"):
                out["hex16"].append((i, m.group(0)[:24]))
        if ASSERT_RE.search(ln):
            big = [t for t in INT_RE.findall(ln)
                   if t.lower().startswith("0x") or int(t.replace("_", "")) >= 1000]
            big = [t for t in big if not re.fullmatch(r"[0-9a-fA-F]{16,}", t)]
            if big and not allowed(path, ln, "parameter"):
                out["assert_num"].append((i, ln.strip()[:100]))
            if (TOL_RE.search(ln) or FLOAT_RE.search(ln)) \
                    and not allowed(path, ln, "parameter"):
                out["toler"].append((i, ln.strip()[:100]))
    # Vector blocks: initializer-like balanced {} (cpp) / [] (py) regions
    # with >= 4 numeric literals. A region is initializer-like when the char
    # before the opener is NOT ')' (rules out TEST_CASE/function/if bodies)
    # and the start line is not a namespace/struct/class/enum opener. Stack
    # based: nested inits fold into the outermost init region (kTones counts
    # once, not once per pair); inits nested in non-init bodies (TEST_CASE)
    # still count. Registered carve-out uses the block's start-line context.
    # (String tables (e) use the same region shape via _str_tables above.)
    opens, closes = ("{", "}") if not path.endswith(".py") else ("[", "]")
    notre = re.compile(r"^\s*(namespace|struct|class|enum)\b")
    stack = []  # [start_line, is_init, buf, parent_is_init]
    prev_sig = ""  # significant chars before the opener (current + prev line)
    for i, ln in enumerate(lines, 1):
        for ch in ln:
            if ch == opens:
                is_init = True
                if prev_sig.endswith(")") or prev_sig.endswith("else"):
                    is_init = False
                if notre.search(raw_lines[i - 1]):
                    is_init = False
                parent_init = any(fr[1] for fr in stack)
                stack.append([i, is_init, "", parent_init])
                prev_sig = ""
            elif ch == closes and stack:
                s, is_init, buf, parent_init = stack.pop()
                if is_init and not parent_init:
                    nums = [t for t in INT_RE.findall(buf)
                            if not re.fullmatch(r"[0-9a-fA-F]{16,}", t)]
                    n = len(nums) + len(FLOAT_RE.findall(buf))
                    ctx = raw_lines[s - 1] + " " + (
                        raw_lines[s - 2] if s >= 2 else "")
                    if n >= 4 and not allowed(path, ctx, "registered") \
                            and not allowed(path, ctx, "parameter"):
                        out["vectors"] += 1
                        out["vec_elems"] += n
                        out["vec_blocks"].append((s, i, n,
                                                 raw_lines[s - 1].strip()[:80]))
            else:
                if ch.strip():
                    prev_sig += ch
                for fr in stack:
                    fr[2] += ch
        prev_sig = prev_sig[-24:]
    for s, e, n, t in _str_tables(path, raw_lines):
        out["strings"] += 1
        out["str_elems"] += n
        out["str_blocks"].append((s, e, n, t))
    return out


def census_all(root):
    files = sorted(glob.glob(os.path.join(root, "tests", "*.cpp"))
                   + glob.glob(os.path.join(root, "training", "tests", "*.py")))
    rows = []
    for path in files:
        rel = os.path.relpath(path, root).replace(os.sep, "/")
        try:
            c = census_file(path)
        except OSError as e:
            print("%s: UNREADABLE %s" % (rel, e))
            continue
        rows.append((rel, c))
    return rows


def totals_for(root):
    return RATCHET.totals_of(census_all(root))


def evaluate(root):
    return RATCHET.evaluate_rows(census_all(root))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default=_REPO)
    args = ap.parse_args(sys.argv[1:] if argv is None else argv)
    rows = census_all(args.root)
    totals = RATCHET.totals_of(rows)
    print("file | digest64 | hex16+ | vectors(elems) | strings(elems) | assert>=1000 | toler")
    for rel, c in rows:
        if c["digest64"] or c["hex16"] or c["vectors"] or c["strings"] or c["assert_num"] or c["toler"]:
            print("%s | %d | %d | %d(%d) | %d(%d) | %d | %d" % (
                rel, len(c["digest64"]), len(c["hex16"]),
                c["vectors"], c["vec_elems"], c["strings"], c["str_elems"],
                len(c["assert_num"]), len(c["toler"])))
            for i, s in c["digest64"] + c["hex16"]:
                print("    L%d digest: %s" % (i, s))
            for i, s in c["assert_num"]:
                print("    L%d assert-num: %s" % (i, s))
            for i, s in c["toler"]:
                print("    L%d toler: %s" % (i, s))
            for s, e, n, t in c["vec_blocks"]:
                print("    L%d-%d vector(%d): %s" % (s, e, n, t))
            for s, e, n, t in c["str_blocks"]:
                print("    L%d-%d strings(%d): %s" % (s, e, n, t))
    print("TOTAL digest64=%d hex16+=%d vectors=%d(elems=%d) strings=%d(elems=%d) assert>=1000=%d toler=%d"
          % (totals["digest64"], totals["hex16"], totals["vectors"],
             totals["vec_elems"], totals["strings"], totals["str_elems"],
             totals["assert_num"], totals["toler"]))
    print("MANUAL parity entries: %d (see MANUAL_PARITY in this script)" % len(MANUAL_PARITY))
    failures, notes = RATCHET.evaluate_rows(rows)
    for note in notes:
        print("NOTE: %s" % note)
    for msg in failures:
        print("lint_off_golden: FAIL: %s" % msg)
    if failures:
        print("lint_off_golden: FAIL (hard-zero + per-file/total ratchet)")
        return 1
    print("lint_off_golden: PASS (hard-zero digest64/hex16+ = 0; the "
          "per-file and total ratchets hold)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
