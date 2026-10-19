# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""B7 permanent guard - the MSVC C2059 quirk probe (self-retiring).

The quirk: `docs/measurements/s3-quirks.md` (status CAUSE UNESTABLISHED)
records that one-line inner-expression mutations of the `sseed` initializer
at `src/inference/candidate_model.cpp` fail under MSVC with
`error C2059: syntax error: ')'` - an opaque diagnostic with no pointer to
the explanation. Because the cause is unestablished, this guard pins the
OUTCOME, not a cause: it compiles the statement shapes and asserts what the
current MSVC does with them.

Run (from anywhere):
    py -3 tools/c2059_probe/probe_c2059.py
    py -3 tools/c2059_probe/probe_c2059.py --require-msvc   # CI form

Exit codes:
    0  PASS - the outcome is the expected one (the quirk still reproduces).
    1  FAIL - the outcome CHANGED (a form that used to compile no longer
       does, or the diagnostic is no longer C2059). The record needs a new
       entry; do NOT silently accept it.
    1  RETIRE - the record's repro form now COMPILES: MSVC no longer emits
       C2059, so the quirk is gone and the constraint in the record (and
       this probe) can be retired. The probe says so out loud, on purpose.
    2  SKIP - no MSVC toolchain found (nothing to assert). With
       --require-msvc a missing toolchain is a FAIL instead (CI form).

The probe needs NO build tree and NO project headers: the witness TU
(`c2059_probe.cpp`) carries the statement shapes itself.
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TU_PATH = os.path.join(HERE, "c2059_probe.cpp")
RECORD = "docs/measurements/s3-quirks.md"

# (label, -D switch or None, expectation)
#   "compile" -> cl must succeed
#   "C2059"   -> cl must fail AND the diagnostic must carry C2059
VARIANTS = (
    ("one-line, balanced", None, "compile"),
    ("one-line, record repro form", "HF_PROBE_MUTATION", "C2059"),
    ("one-line mutation, balanced parens", "HF_PROBE_MUTATION_BAL", "compile"),
    ("two-statement (record working form)", "HF_PROBE_TWOSTATEMENT", "compile"),
)

CL_FLAGS = ["/nologo", "/c", "/EHsc", "/std:c++20", "/utf-8", "/W3"]

VERSION_RE = re.compile(r"Version ([0-9.]+) for ([A-Za-z0-9]+)")


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


def _cl_in_vs(vs_root):
    tools = os.path.join(vs_root, "VC", "Tools", "MSVC")
    if not os.path.isdir(tools):
        return None
    best = None
    for ver in sorted(os.listdir(tools), reverse=True):
        cand = os.path.join(tools, ver, "bin", "Hostx64", "x64", "cl.exe")
        if os.path.isfile(cand):
            best = cand
            break
    return best


def find_toolchain():
    """Return (cl_path, env_or_None). (None, None) when MSVC is absent."""
    if os.name != "nt":
        return None, None
    on_path = shutil.which("cl")
    if on_path:
        return on_path, None
    vswhere = _vswhere_path()
    if not vswhere:
        return None, None
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
        if "INCLUDE" not in env:
            # vcvars did not set up the SDK include path - this install is
            # not usable for a compile probe.
            continue
        return cl, env
    return None, None


def compiler_version(cl, env):
    proc = subprocess.run([cl], capture_output=True, env=env)
    match = VERSION_RE.search(_decode(proc.stdout + proc.stderr))
    if match:
        return "MSVC %s for %s" % (match.group(1), match.group(2))
    return "MSVC (version banner unavailable)"


def compile_variant(cl, env, define, workdir):
    """Compile the witness TU in one shape; return (returncode, output)."""
    src = os.path.join(workdir, "c2059_probe.cpp")
    shutil.copyfile(TU_PATH, src)
    obj = os.path.join(workdir, "c2059_probe.obj")
    cmd = [cl] + CL_FLAGS
    if define:
        cmd.append("/D" + define)
    cmd += [src, "/Fo" + obj]
    proc = subprocess.run(cmd, capture_output=True, cwd=workdir, env=env)
    return proc.returncode, _decode(proc.stdout + proc.stderr)


def first_error_line(output):
    for line in output.splitlines():
        if "error C" in line:
            return line.strip()
    return "(no error line found)"


def main(argv):
    parser = argparse.ArgumentParser(
        description="B7 probe: pin the MSVC C2059 outcome (self-retiring).")
    parser.add_argument("--require-msvc", action="store_true",
                        help="fail (instead of skipping) when no MSVC "
                             "toolchain is found (CI form)")
    args = parser.parse_args(argv)

    print("[c2059] B7 probe - record: %s" % RECORD)
    cl, env = find_toolchain()
    if cl is None:
        msg = ("[c2059] SKIP: no MSVC toolchain found - the probe cannot "
               "assert the outcome")
        if args.require_msvc:
            print(msg)
            print("[c2059] FAIL: --require-msvc was given and MSVC is absent")
            return 1
        print(msg)
        return 2

    print("[c2059] compiler: %s" % compiler_version(cl, env))
    print("[c2059] witness TU: %s" % os.path.relpath(TU_PATH, HERE))
    results = []
    with tempfile.TemporaryDirectory() as workdir:
        for (label, define, expect) in VARIANTS:
            code, out = compile_variant(cl, env, define, workdir)
            if expect == "compile":
                ok = (code == 0)
            else:
                ok = (code != 0) and ("C2059" in out)
            results.append((label, expect, code, out, ok))
            state = "as expected" if ok else "CHANGED"
            print("[c2059]   %-38s expect=%-8s cl_exit=%d  %s"
                  % (label, expect, code, state))
            if not ok:
                print("[c2059]     compiler said: %s" % first_error_line(out))

    # The repro form compiling again == MSVC stopped emitting C2059.
    repro_ok = None
    for (label, expect, code, out, ok) in results:
        if expect == "C2059":
            repro_ok = (code == 0)
            break
    if repro_ok:
        print("[c2059] RETIRE: the record's repro form now COMPILES - MSVC no "
              "longer emits C2059.")
        print("[c2059]   The quirk is gone: drop the constraint in %s and "
              "delete tools/c2059_probe/." % RECORD)
        return 1

    bad = [r for r in results if not r[4]]
    if bad:
        print("[c2059] FAIL: the outcome CHANGED (%d of %d shapes). The "
              "record %s needs a new entry - do not silently accept it."
              % (len(bad), len(results), RECORD))
        return 1

    print("[c2059] PASS: the outcome is unchanged - the record's repro form "
          "still fails with C2059 and every other shape compiles.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
