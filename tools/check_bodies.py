# S3 body-identity guard: proves a moved function body is byte-identical
# (modulo whitespace/comments plus an explicit allowlist) between the pinned
# pre-cut revision and its new translation unit. STDLIB ONLY.
#
# Usage: py -3 tools/check_bodies.py [--root DIR] [--config FILE]
# Exit 0 when every mapped function matches, 1 otherwise (prints the first
# divergence with line context). No repo writes, ever.
import argparse
import json
import os
import re
import subprocess
import sys


def repo_text_at_rev(root, rev, path):
    # The decode is EXPLICIT (never the locale): `text=True` alone decodes
    # the child's bytes with the ANSI code page, which RAISED inside the
    # reader thread on a non-ASCII path.
    p = subprocess.run(
        ["git", "-C", root, "show", "%s:%s" % (rev, path)],
        capture_output=True, text=True, encoding="utf-8",
        errors="surrogateescape")
    if p.returncode != 0:
        raise SystemExit("check_bodies: git show failed for %s:%s" % (rev, path))
    return p.stdout


def strip_comments(s):
    s = re.sub(r"/\*.*?\*/", " ", s, flags=re.S)
    s = re.sub(r"//[^\n]*", " ", s)
    return s


def normalize(s):
    return re.sub(r"\s+", " ", strip_comments(s)).strip()


def extract(text, sig):
    """Find `sig + '(' ... balanced-brace body. Returns (start_line, end_line, raw)."""
    needle = sig + "("
    idx = text.find(needle)
    if idx < 0:
        return None
    if text.find(needle, idx + 1) >= 0:
        raise SystemExit("check_bodies: signature %r is not unique" % sig)
    brace = text.find("{", idx)
    if brace < 0:
        return None
    depth = 0
    i = brace
    while i < len(text):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                raw = text[idx:i + 1]
                start_line = text.count("\n", 0, idx) + 1
                end_line = text.count("\n", 0, i) + 1
                return (start_line, end_line, raw)
        i += 1
    return None


def first_diff(a, b, width=80):
    n = min(len(a), len(b))
    i = 0
    while i < n and a[i] == b[i]:
        i += 1
    lo = max(0, i - width)
    return ("old[%d:]: ...%s..." % (lo, a[lo:i + width]),
            "new[%d:]: ...%s..." % (lo, b[lo:i + width]))


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    default_root = os.path.dirname(here)
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=default_root)
    ap.add_argument("--git-root", default=None,
                    help="git repo for old-rev lookup (defaults to --root)")
    ap.add_argument("--config", default=os.path.join(default_root, "tools",
                                                     "check_bodies_s3.json"))
    args = ap.parse_args()
    git_root = args.git_root or args.root
    with open(args.config, encoding="utf-8") as f:
        cfg = json.load(f)
    failed = 0
    for name, m in cfg["functions"].items():
        sig = m["sig"]
        old = m["old"]
        new = m["new"]
        old_text = repo_text_at_rev(git_root, old["rev"], old["path"])
        with open(os.path.join(args.root, new["path"]), encoding="utf-8") as f:
            new_text = f.read()
        eo = extract(old_text, sig)
        en = extract(new_text, sig)
        if eo is None:
            print("FAIL %s: signature not found in %s:%s" % (name, old["rev"], old["path"]))
            failed += 1
            continue
        if en is None:
            print("FAIL %s: signature not found in %s" % (name, new["path"]))
            failed += 1
            continue
        ok = True
        if (eo[0], eo[1]) != (old["start"], old["end"]):
            print("FAIL %s: old range is %d-%d, config says %d-%d"
                  % (name, eo[0], eo[1], old["start"], old["end"]))
            ok = False
        if (en[0], en[1]) != (new["start"], new["end"]):
            print("FAIL %s: new range is %d-%d, config says %d-%d"
                  % (name, en[0], en[1], new["start"], new["end"]))
            ok = False
        raw_old = eo[2]
        for pair in m.get("allow", []):
            if pair["old"] not in raw_old:
                print("FAIL %s: allowlist old-text not found: %r" % (name, pair["old"]))
                ok = False
            raw_old = raw_old.replace(pair["old"], pair["new"])
        no, nn = normalize(raw_old), normalize(en[2])
        if no != nn:
            print("FAIL %s: normalized bodies differ" % name)
            a, b = first_diff(no, nn)
            print("  " + a)
            print("  " + b)
            ok = False
        if ok:
            print("OK %s: %s:%d-%d == %s:%d-%d (allowlist %d)"
                  % (name, old["path"], eo[0], eo[1], new["path"], en[0], en[1],
                     len(m.get("allow", []))))
        else:
            failed += 1
    if failed:
        print("check_bodies: %d FAIL" % failed)
        return 1
    print("check_bodies: all green")
    return 0


if __name__ == "__main__":
    sys.exit(main())
