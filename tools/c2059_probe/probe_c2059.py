# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""B7 permanent guard - the `sseed` C2059 probe (cause ESTABLISHED).

THE CAUSE (established 2026-10-19, record: docs/measurements/s3-quirks.md):
the scratch mutations that once failed at the `sseed` initializer in
src/inference/candidate_model.cpp with `error C2059: syntax error: ')'`
each carried extra closing paren(s) - one, except the record's fourth
repro form, which carries two. That is a plain C++ syntax error - any
compiler rejects it - NOT an MSVC quirk. The well-formed one-line form
COMPILES, which is what retired the old "no single-line inner-expression
mutations at this site" constraint.

WHAT THIS PROBE PINS (it compiles the REAL site file, not a copy of it):

  (a) the site TU compiles AS IT STANDS;
  (b) the well-formed ONE-LINE forms compile - the site's two lines joined
      AND an inner-expression mutation on one line
      (`runner_seed(p, index + 1)`). That is the fact that retired the old
      "no single-line inner-expression mutations" constraint: either form is
      fine. B3 moved the initializer from the inline additive expression to
      `runner_seed(p, index)`; the shapes below track the new site while the
      historical repro text stays in the record;
  (c) each of the four recorded MALFORMED forms fails to compile. Only
      the FAILURE is asserted: "C2059" is not a property of the compiler
      but of the typo, so the diagnostic text is printed, never pinned;
  (d) the two-statement form (the record's RECOMMENDED shape for scratch
      mutations - one paren less to typo) compiles.

VERDICTS - distinct exit codes, so a spurious verdict is distinguishable
from a real one:

  0  PASS         every fact above holds.
  1  FAIL         a fact does not hold: the site or the toolchain broke.
  2  SKIP         no MSVC toolchain found (nothing to assert; not an
                  error). With --require-msvc this becomes a FAIL.
  3  PROBE-BROKEN the probe could not build the variant it wanted: its
                  anchor no longer matches the site, or a variant's text
                  does not match its declared expectation. This is a PROBE
                  bug, never a finding about the site or the compiler.
  4  RETIRE       the well-formed one-line form stopped compiling: the
                  premise that retired the constraint broke. Loud on
                  purpose - the constraint must NOT stay retired silently.

Run (from anywhere):
    py -3 tools/c2059_probe/probe_c2059.py
    py -3 tools/c2059_probe/probe_c2059.py --require-msvc   # CI form
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))  # the CI-safe console helper lives in tools/
import ci_encoding  # noqa: E402  (the CI-safe console helper)

REPO_ROOT = os.path.dirname(os.path.dirname(HERE))
SITE_REL = os.path.join("src", "inference", "candidate_model.cpp")
RECORD_REL = os.path.join("docs", "measurements", "s3-quirks.md")
SITE = os.path.join(REPO_ROOT, SITE_REL)

# The include dirs of the harmony_forge_inference target (see
# src/inference/CMakeLists.txt: target_include_directories PUBLIC
# <this dir> and <this dir>/../core, plus the repo's `src` root). The
# probe uses the repo's OWN directories - it never reads a build tree.
INCLUDE_DIRS = (
    os.path.join("src", "inference"),
    os.path.join("src", "core"),
    "src",
)

# The project defines of the production build, minus HARMONY_FORGE_WITH_ONNX:
# the offline-stub configuration (-DHARMONY_FORGE_WITH_ONNX=OFF, a
# first-class option of this repo) is the one a build-tree-free probe can
# reproduce. The inference HEADERS include no ONNX Runtime headers
# (onnx_runner.h / ort_logits.h / sampler.h), so the `sseed` statement is
# compiled from the same headers either way.
DEFINES = ("WIN32", "_WINDOWS", "NDEBUG")

CL_FLAGS = ("/nologo", "/c", "/EHsc", "/std:c++20", "/utf-8", "/W3")

# The site statement the record's mutations were applied to. The probe
# REPLACES this whole statement. If the site text ever changes, the
# anchor stops matching and the probe reports PROBE-BROKEN - it never
# silently compiles an unmutated file and calls it a pass.
SITE_STATEMENT_RE = re.compile(
    r"    const std::uint64_t sseed =\s*"
    r"static_cast<std::uint64_t>\(runner_seed\(p, index\)\);")

# The well-formed one-line form: the shape the old constraint forbade and
# the probe proves to compile.
ONE_LINE = ("    const std::uint64_t sseed = static_cast<std::uint64_t>("
            "runner_seed(p, index));")

# The same, with an inner-expression mutation on ONE line
# (`runner_seed(p, index + 1)`): this is the shape the retired constraint
# actually banned ("NO single-line inner-expression mutations"), so it is the
# retirement proof itself - either form is fine.
ONE_LINE_INNER = ("    const std::uint64_t sseed = static_cast<std::uint64_t>("
                  "runner_seed(p, index + 1));")

# The two-statement form of the record: the RECOMMENDED shape for scratch
# mutations (one closing paren less to typo).
TWO_STATEMENT = ("    const unsigned sseed32 = runner_seed(p, index);\n"
                 "    const std::uint64_t sseed = sseed32 + 1u;")

# The four recorded repro forms (docs/measurements/s3-quirks.md), each
# with the extra closing paren(s) that made it malformed. The paren delta
# of each record line is part of the variant's declaration: repro #1-#3
# carry ONE extra closing paren, repro #4 carries TWO (2 `(` and 4 `)`).
# Labels show the B3 re-expressed forms; the literal historical text lives
# in docs/measurements/s3-quirks.md.
MALFORMED = (
    ("malformed-1", "record repro #1 (runner_seed(p, index + 1))",
     "    const std::uint64_t sseed =\n"
     "        static_cast<std::uint64_t>(runner_seed("
     "p, index + 1)));", -1),
    ("malformed-2", "record repro #2 (runner_seed(p, index + 0))",
     "    const std::uint64_t sseed =\n"
     "        static_cast<std::uint64_t>(runner_seed("
     "p, index + 0)));", -1),
    ("malformed-3", "record repro #3 (runner_seed(p, index ^ 1))",
     "    const std::uint64_t sseed =\n"
     "        static_cast<std::uint64_t>(runner_seed("
     "p, index ^ 1)));", -1),
    ("malformed-4", "record repro #4 (runner_seed(p, index) + 1u)",
     "    const std::uint64_t sseed =\n"
     "        static_cast<std::uint64_t>(runner_seed("
     "p, index) + 1u)));", -2),
)

# (key, label, expectation, replacement or None, paren delta of the
#  replacement). "compile" -> cl must succeed, "compile-error" -> cl must
#  fail. The paren delta is the SELF-CHECK of each variant's text: a
#  well-formed statement has 0, a malformed one the extra closing paren(s)
#  of the record's line. A variant whose text does not match its
#  declaration is a PROBE bug and is reported as such - never as a site
#  finding.
VARIANTS = (
    ("site", "site as-is (the repo's file, unmodified)", "compile", None, 0),
    ("one-line", "well-formed ONE-LINE form (the site's two lines joined)",
     "compile", ONE_LINE, 0),
    ("one-line-inner",
     "well-formed inner-expression mutation on ONE line (runner_seed(p, index + 1))",
     "compile", ONE_LINE_INNER, 0),
    ("two-statement", "two-statement form (record's recommended shape)",
     "compile", TWO_STATEMENT, 0),
) + tuple((key, label, "compile-error", text, delta)
          for (key, label, text, delta) in MALFORMED)

EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_SKIP = 2
EXIT_PROBE_BROKEN = 3
EXIT_RETIRE = 4


def _decode(raw):
    """Decode a compiler stream without ever raising (ASCII tokens survive)."""
    try:
        return raw.decode("mbcs")
    except (LookupError, UnicodeDecodeError):
        return raw.decode("utf-8", "replace")


def _vswhere_path():
    for base in (os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
                 os.environ.get("ProgramFiles", r"C:\Program Files")):
        cand = os.path.join(base, "Microsoft Visual Studio", "Installer",
                            "vswhere.exe")
        if os.path.isfile(cand):
            return cand
    return None


def _vcvars_bat(vs_root):
    build = os.path.join(vs_root, "VC", "Auxiliary", "Build")
    for name in ("vcvars64.bat", "vcvarsall.bat"):
        cand = os.path.join(build, name)
        if os.path.isfile(cand):
            return cand
    return None


def _capture_env(vcvars):
    """Run vcvars in a temp batch file and capture the resulting env.

    The batch file (not an inline `cmd /c "call ..."` string) is what makes
    the quoting survive: the install path carries spaces, and cmd.exe does
    not understand the backslash escaping that subprocess uses on Windows.
    """
    fd, bat = tempfile.mkstemp(suffix=".cmd")
    os.close(fd)
    try:
        with open(bat, "w", newline="") as fh:
            fh.write("@echo off\r\n")
            fh.write('call "%s" >nul 2>&1\r\n' % vcvars)
            fh.write("set\r\n")
        proc = subprocess.run(["cmd", "/c", bat], capture_output=True)
        env = {}
        for line in _decode(proc.stdout).splitlines():
            if "=" not in line or line.startswith("="):
                continue
            key, _, value = line.partition("=")
            env[key.upper()] = value
        return env
    finally:
        try:
            os.remove(bat)
        except OSError:
            pass


def _env_has_msvc_paths(env) -> bool:
    """True when `env` carries the MSVC include/lib paths.

    A `cl.exe` that is only on PATH has no INCLUDE/LIB of its own: without
    them every compile fails with "cannot open include file", which says
    nothing about the site under test. A usable environment is the one a
    Developer Prompt (or vcvars) sets up.
    """
    return bool(env.get("INCLUDE")) and bool(env.get("LIB"))


def _cl_in_vs(vs_root):
    tools = os.path.join(vs_root, "VC", "Tools", "MSVC")
    if not os.path.isdir(tools):
        return None
    for ver in sorted(os.listdir(tools), reverse=True):
        cand = os.path.join(tools, ver, "bin", "Hostx64", "x64", "cl.exe")
        if os.path.isfile(cand):
            return cand
    return None


def _bare_cl(on_path):
    """The PATH `cl` with NO set-up environment.

    It cannot compile the site (no INCLUDE/LIB), but it IS the compiler the
    machine has, so it is kept as the last resort: the probe then reports a
    real compile attempt instead of pretending that MSVC is absent.
    """
    if not on_path:
        return None, None
    print("[sseed] NOTE: the `cl` on PATH has no INCLUDE/LIB - the "
          "environment is not set up (a Developer Prompt or vcvars would "
          "set it up); the compile below may fail for that reason")
    return on_path, None


def find_toolchain():
    """Return (cl_path, env_or_None). (None, None) when MSVC is absent.

    A `cl` that is found on PATH is used ONLY when the environment is set
    up (INCLUDE + LIB): a bare cl.exe has neither, and every compile would
    then fail for a reason that has nothing to do with the site. When the
    PATH `cl` is not usable the discovery falls through to the vswhere +
    vcvars path, which builds a complete environment.
    """
    if os.name != "nt":
        return None, None
    on_path = shutil.which("cl")
    if on_path and _env_has_msvc_paths(os.environ):
        return on_path, None
    vswhere = _vswhere_path()
    if not vswhere:
        return _bare_cl(on_path)
    proc = subprocess.run(
        [vswhere, "-latest", "-products", "*", "-requires",
         "Microsoft.VisualStudio.Component.VC.Tools.x86.x64",
         "-property", "installationPath"], capture_output=True)
    roots = [r.strip() for r in _decode(proc.stdout).splitlines() if r.strip()]
    for root in roots:
        if not os.path.isdir(root):
            continue
        cl = _cl_in_vs(root)
        vcvars = _vcvars_bat(root)
        if cl is None or vcvars is None:
            continue
        env = dict(os.environ)
        env.update(_capture_env(vcvars))
        if not _env_has_msvc_paths(env):
            # vcvars did not set up the SDK include/lib paths - this
            # install is not usable for a compile probe.
            continue
        return cl, env
    return _bare_cl(on_path)


def compiler_version(cl, env):
    proc = subprocess.run([cl], capture_output=True, env=env)
    match = re.search(r"Version ([0-9.]+) for ([A-Za-z0-9]+)",
                      _decode(proc.stdout + proc.stderr))
    if match:
        return "MSVC %s for %s" % (match.group(1), match.group(2))
    return "MSVC (version banner unavailable)"


def read_site():
    """The site source, with the line endings normalised to \\n."""
    with open(SITE, "rb") as fh:
        raw = fh.read()
    text = raw.decode("utf-8")
    return text.replace("\r\n", "\n")


def build_variant(text, replacement):
    """Apply a statement replacement; return (new_text, applied)."""
    if replacement is None:
        return text, True
    # A lambda replacement keeps the text literal (no backslash escapes).
    new_text, count = SITE_STATEMENT_RE.subn(
        lambda _m: replacement, text, count=1)
    return new_text, (count == 1)


def compile_source(cl, env, source_text, workdir):
    """Compile the (possibly mutated) site source; return (code, output)."""
    src = os.path.join(workdir, "candidate_model.cpp")
    data = source_text.replace("\n", "\r\n").encode("utf-8")
    with open(src, "wb") as fh:
        fh.write(data)
    obj = os.path.join(workdir, "candidate_model.obj")
    cmd = [cl] + list(CL_FLAGS)
    for define in DEFINES:
        cmd.append("/D" + define)
    for inc in INCLUDE_DIRS:
        cmd += ["/I", os.path.join(REPO_ROOT, inc)]
    cmd += [src, "/Fo" + obj]
    proc = subprocess.run(cmd, capture_output=True, cwd=workdir, env=env)
    return proc.returncode, _decode(proc.stdout + proc.stderr)


def first_error_line(output):
    for line in output.splitlines():
        if "error C" in line:
            return line.strip()
    return "(no error line found)"


def check_variant_text(replacement, delta):
    """Self-check of a variant's text: the declared paren delta must hold."""
    if replacement is None:
        return True
    opens = replacement.count("(")
    closes = replacement.count(")")
    return (opens - closes) == delta


def main(argv):
    # BEFORE the parser: argparse prints its OWN errors (a bad flag, a
    # missing value) through the console, so a cp1252 console must already
    # be hardened when the parse fails - otherwise the usage message dies
    # with a traceback instead of the error.
    ci_encoding.harden_console()  # the console must never raise on a path
    parser = argparse.ArgumentParser(
        description="B7 probe: the `sseed` statement compiles on the real "
                    "site, and the malformed forms fail to compile.")
    parser.add_argument("--require-msvc", action="store_true",
                        help="fail (instead of skipping) when no MSVC "
                             "toolchain is found (CI form)")
    args = parser.parse_args(argv)

    print("[sseed] B7 probe - record: %s" % RECORD_REL.replace("\\", "/"))
    print("[sseed] site: %s" % SITE_REL.replace("\\", "/"))

    # --- the probe's own self-checks (a broken probe is NOT a finding) ---
    for (key, label, expectation, replacement, delta) in VARIANTS:
        if not check_variant_text(replacement, delta):
            print("[sseed] PROBE-BROKEN: variant %r (%s) has paren delta %d, "
                  "expected %d - the variant table is wrong."
                  % (key, label,
                     (replacement.count("(") - replacement.count(")"))
                     if replacement else 0, delta))
            return EXIT_PROBE_BROKEN

    cl, env = find_toolchain()
    if cl is None:
        print("[sseed] SKIP: no MSVC toolchain found - the probe cannot "
              "assert the outcome")
        if args.require_msvc:
            print("[sseed] FAIL: --require-msvc was given and MSVC is absent")
            return EXIT_FAIL
        return EXIT_SKIP
    print("[sseed] compiler: %s" % compiler_version(cl, env))

    site_text = read_site()
    if len(SITE_STATEMENT_RE.findall(site_text)) != 1:
        print("[sseed] PROBE-BROKEN: the anchor (the `sseed` statement) does "
              "not match the site exactly once - update the probe.")
        return EXIT_PROBE_BROKEN

    results = []
    with tempfile.TemporaryDirectory() as workdir:
        for (key, label, expectation, replacement, delta) in VARIANTS:
            source, applied = build_variant(site_text, replacement)
            if not applied:
                print("[sseed] PROBE-BROKEN: variant %r could not be applied "
                      "to the site - update the probe." % key)
                return EXIT_PROBE_BROKEN
            if replacement is not None and source == site_text:
                print("[sseed] PROBE-BROKEN: variant %r did not change the "
                      "site - update the probe." % key)
                return EXIT_PROBE_BROKEN
            code, out = compile_source(cl, env, source, workdir)
            ok = (code == 0) if expectation == "compile" else (code != 0)
            results.append((key, label, expectation, code, ok))
            print("[sseed]   %-46s expect=%-13s cl_exit=%d  %s"
                  % (label, expectation, code,
                     "as expected" if ok else "DEVIATION"))
            if not ok:
                print("[sseed]     compiler said: %s" % first_error_line(out))

    def outcome(key):
        for entry in results:
            if entry[0] == key:
                return entry
        return None

    # (a) the site itself must compile - if it does not, the site or the
    #     toolchain broke, which is the most fundamental finding.
    site_entry = outcome("site")
    if site_entry is not None and not site_entry[4]:
        print("[sseed] FAIL: the site TU does not compile as it stands - the "
              "site or the toolchain broke. Fix that first.")
        return EXIT_FAIL

    # (b) the well-formed one-line forms must compile: this is the fact that
    #     retired the old constraint (the site's two lines joined, and an
    #     inner-expression mutation on one line). If they stop compiling,
    #     the premise of the retirement broke - say so loudly.
    for key in ("one-line", "one-line-inner"):
        entry = outcome(key)
        if entry is not None and not entry[4]:
            print("[sseed] RETIRE: the well-formed ONE-LINE form stopped "
                  "compiling (variant %r) - the premise that retired the "
                  "constraint broke." % key)
            print("[sseed]   The site or the toolchain changed: re-open the "
                  "constraint in %s before trusting it."
                  % RECORD_REL.replace("\\", "/"))
            return EXIT_RETIRE

    bad = [r for r in results if not r[4]]
    if bad:
        print("[sseed] FAIL: %d of %d shapes deviate - the site or the "
              "toolchain changed; %s needs a new entry."
              % (len(bad), len(results), RECORD_REL.replace("\\", "/")))
        return EXIT_FAIL

    print("[sseed] PASS: the site compiles as it stands, both well-formed "
          "one-line forms compile (lines joined and an inner-expression "
          "mutation on one line), and all four malformed forms fail to "
          "compile (plain C++ syntax errors, not an MSVC quirk).")
    return EXIT_PASS


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
