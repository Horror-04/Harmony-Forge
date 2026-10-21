# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Regression tests for the CI locale crash (the first GitHub Actions run).

THE FAILURE (the repository's FIRST GitHub Actions run, gates job step #6,
``python tools/lint_golden_manifest.py``)::

    Exception in thread Thread-3 (_readerthread):
      File ".../subprocess.py", line 1599, in _readerthread
        buffer.append(fh.read())
      File ".../encodings/cp1252.py", line 23, in decode
        return codecs.charmap_decode(input, self.errors, decoding_table)[0]
      AttributeError: 'NoneType' object has no attribute 'split'
      File "tools/lint_golden_manifest.py", line 260, in _git_tracked_paths
        return {p for p in out.stdout.split("\\0") if p}

ROOT CAUSE: ``subprocess.run(..., text=True)`` WITHOUT an ``encoding=``
decodes the child's bytes with the LOCALE encoding. The ``windows-2022``
runner's Python 3.12 uses the ANSI code page (cp1252), and the repository
tracked a file whose NAME is not ASCII, so decoding git's ``ls-files -z``
output RAISED inside the reader thread, ``stdout`` ended up ``None`` and
the lint crashed. On the dev machine the locale is cp1251, where the same
bytes only MOJIBAKE - so the bug never showed locally.

THE FIX: every captured subprocess decodes EXPLICITLY
(``encoding="utf-8", errors="surrogateescape"``). Git emits UTF-8 paths and
``surrogateescape`` keeps an undecodable byte representable instead of
raising. The tests below:

  1. a temp repo with a tracked NON-ASCII name: the lint must report a
     NORMAL verdict (never an AttributeError);
  2. the same with an unregistered non-ASCII artifact: the coverage rule
     may flag it - a normal verdict too (exit 1 by the rules);
  3. the same with the locale FORCED to cp1252 (the runner's condition):
     the lint must still work;
  4. a repo-wide GUARD: no ``tools/**/*.py`` may call subprocess with
     ``text=True`` and no explicit ``encoding=``. The guard's LOGIC lives
     in ``tools/lint_locale_independence.py`` (a script, so the CI can
     run it as a blocking step); the test below calls that script's
     function, so the rule is implemented once.

THE SECOND FAILURE - the OUTPUT dimension (the CI's SECOND runner
execution, the new "Python gate tests" step)::

    File "tools/lint_golden_manifest.py", line 833, in main
      print(f"lint_golden_manifest: FAIL: {msg}")
    File ".../encodings/cp1252.py", line 19, in encode
    UnicodeEncodeError: 'charmap' codec can't encode characters in position 49-59'

The previous wave fixed the INPUT side (the decode); the OUTPUT side still
went through the CONSOLE, so the lint died with a traceback instead of
reporting its verdict. Case 3 passed locally ONLY because the local
console is cp1251: it forced the LOCALE (the decode) but never the STDOUT
ENCODING (the print). The fix is ``tools/ci_encoding.py``: every tool
hardens its console (``ci_encoding.harden_console()``) so an unencodable
character is REPLACED (an escape) instead of raising - the console's own
encoding is kept and the verdict + the exit code always come out. The
helper's own unit-level proof lives in ``tools/tests/test_console_encoding.py``
(split out of this file, which sits at the 500-line pin).
NOTE on the locale knob: since Python 3.11 ``io.TextIOWrapper`` (and so
subprocess) asks the LOCALE MODULE for the encoding - ``locale.getencoding()``
(PEP 597) - and NOT ``locale.getpreferredencoding()`` (which is only a
wrapper around it since 3.11). Both are patched here: ``getencoding`` is
the knob that actually drives the decode, ``getpreferredencoding`` is the
pre-3.11 knob and the one the CI failure is usually described with.
"""

import hashlib
import json
import locale
import os
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
LINT = os.path.join(REPO_ROOT, "tools", "lint_golden_manifest.py")
TOOLS_DIR = os.path.join(REPO_ROOT, "tools")

# The AST GUARD lives in a SCRIPT (tools/lint_locale_independence.py) so
# that it can run as a blocking CI step - while it lived only here, the
# CI never executed it (the workflow has no pytest step). This test is
# the unit-level proof and calls THAT script's function: the scan logic
# exists once, in the script.
sys.path.insert(0, TOOLS_DIR)

import lint_locale_independence as LOCALE  # noqa: E402

# The tracked name that broke the first CI run (Cyrillic).
NON_ASCII_NAME = "методология.txt"

GOLDEN_TXT = b"# synthetic golden\nvalue 42\n"
FIXTURE_JSON = b'{"fixture": true}\n'
MID_BYTES = b"MThd\x00\x00\x00\x06\x00\x00\x00\x01\x00\x60"
TEST_SRC = (b'// synthetic test source\n'
            b'TEST_CASE("synthetic case name", "[x]") { CHECK(true); }\n')
ANCHOR = "synthetic case name"

# The lint process, run with the locale FORCED to cp1252 (the runner's
# condition). The prelude patches the locale module BEFORE the lint runs,
# so every locale-decoded capture inside it uses cp1252.
_LOCALE_PRELUDE = (
    "import locale, runpy, sys\n"
    "locale.getencoding = lambda *a, **k: 'cp1252'\n"
    "locale.getpreferredencoding = lambda *a, **k: 'cp1252'\n"
    "sys.argv = sys.argv[1:]\n"
    "runpy.run_path(sys.argv[0], run_name='__main__')\n"
)

# The OUTPUT dimension: the child's console code page. PYTHONIOENCODING is
# the runner's condition exactly (the windows-2022 runner's Python 3.12
# writes to a cp1252 console with the STRICT handler: a print of a
# non-ASCII path RAISES). The locale above drives the DECODE, this the
# print.
_CP1252_CONSOLE_ENV = {"PYTHONIOENCODING": "cp1252:strict"}

# The premise of the regression, run in a CHILD process: the same bytes
# (U+044F 'ya' in UTF-8) captured with and without an explicit encoding
# under a cp1252 locale. Written as source (not as a call in this file)
# so that the guard test below sees no locale-decoded capture here.
_DECODE_PROBE = """\
import locale
import subprocess
import sys

locale.getencoding = lambda *a, **k: "cp1252"
locale.getpreferredencoding = lambda *a, **k: "cp1252"
CHILD = [sys.executable, "-c",
         "import sys; sys.stdout.buffer.write(bytes([0xd1, 0x8f]))"]
locale_capture = subprocess.run(CHILD, capture_output=True, text=True)
explicit_capture = subprocess.run(CHILD, capture_output=True, text=True,
                                  encoding="utf-8", errors="surrogateescape")
print("LOCALE", ascii(locale_capture.stdout))
print("EXPLICIT", ascii(explicit_capture.stdout))
"""


def _sha(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def _canonical_sha(blob: bytes) -> str:
    """LF-canonical sha256 for text (the registry's convention)."""
    if b"\x00" not in blob:
        blob = blob.replace(b"\r\n", b"\n")
    return _sha(blob)


def _write(path: str, blob: bytes) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(blob)


def _git(root: str, *args: str) -> str:
    proc = subprocess.run(["git", "-C", root] + list(args),
                          capture_output=True, encoding="utf-8",
                          errors="surrogateescape")
    if proc.returncode != 0:
        raise RuntimeError("git %s failed: %s" % (" ".join(args),
                                                  proc.stderr[-400:]))
    return proc.stdout.strip()


def _build_tree(root: str) -> str:
    """Minimal synthetic repo tree (golden + fixture + test + writer stubs)
    with ONE commit, so the lint's commit-resolution check really runs."""
    _write(os.path.join(root, "tests", "golden", "g.txt"), GOLDEN_TXT)
    _write(os.path.join(root, "tests", "golden", "seeds", "s1.mid"), MID_BYTES)
    _write(os.path.join(root, "tests", "fixtures", "f.json"), FIXTURE_JSON)
    _write(os.path.join(root, "tests", "test_x.cpp"), TEST_SRC)
    _write(os.path.join(root, "tools", "gen_x.py"), b"print('gen')\n")
    for tool in ("update_golden_midi.py", "gen_s6_3_fixtures.py"):
        _write(os.path.join(root, "tools", tool), b"# stub writer\n")
    _write(os.path.join(root, "tests", "CMakeLists.txt"),
           b"hf_add_test(test_x test_x.cpp)\n")
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.name", "lint")
    _git(root, "config", "user.email", "lint@example.invalid")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "synthetic tree")
    return _git(root, "rev-parse", "HEAD")


def _manifest(commit: str) -> dict:
    """A clean registry for the synthetic tree (the lint must PASS on it)."""
    capture = ("capture: synthetic capture source@%s (no in-repo writer) - "
               'tests/test_x.cpp "%s"' % (commit, ANCHOR))
    return {
        "in_test": [
            {
                "test": "synthetic golden case (tests/test_x.cpp, [x] "
                        "'synthetic case name')",
                "kind": "in_test",
                "commit": commit + " synthetic tree",
                "produced_by": capture,
                "files": {"tests/golden/g.txt": _canonical_sha(GOLDEN_TXT)},
            },
        ],
        "golden_midi": [
            {
                "seed": 1,
                "file": "tests/golden/seeds/s1.mid",
                "sha256": _sha(MID_BYTES),
                "bytes": len(MID_BYTES),
                "kind": "golden",
                "commit": commit + " synthetic tree",
                "produced_by": capture,
                "files": {"tests/golden/seeds/s1.mid": _sha(MID_BYTES)},
            },
        ],
        "fixtures": [
            {
                "test": "synthetic fixture case (tests/test_x.cpp)",
                "kind": "fixture",
                "commit": commit + " synthetic tree",
                "produced_by": capture,
                "files": {"tests/fixtures/f.json":
                          _canonical_sha(FIXTURE_JSON)},
            },
        ],
    }


def _run_lint(root: str, manifest: str, force_cp1252: bool = False,
              force_cp1252_stdout: bool = False):
    """Run the manifest lint on `root` (as a child process).
    `force_cp1252` forces the child's LOCALE (the decode),
    `force_cp1252_stdout` its CONSOLE ENCODING (the print).
    """
    if force_cp1252:
        cmd = [sys.executable, "-c", _LOCALE_PRELUDE, LINT,
               "--root", root, "--manifest", manifest]
    else:
        cmd = [sys.executable, LINT, "--root", root, "--manifest", manifest]
    env = None
    if force_cp1252_stdout:
        env = dict(os.environ)
        env.update(_CP1252_CONSOLE_ENV)
    return subprocess.run(cmd, capture_output=True, cwd=REPO_ROOT, env=env,
                          encoding="utf-8", errors="surrogateescape")


def _lint_tree(extra_path: str | None = None, force_cp1252: bool = False,
               force_cp1252_stdout: bool = False, manifest_mutator=None):
    """Build the synthetic tree (+ an optional extra tracked file), write the
    registry and run the lint. Returns (tmp, CompletedProcess).
    `manifest_mutator(manifest, commit)` may edit the registry first.
    """
    tmp = tempfile.TemporaryDirectory()
    root = tmp.name
    commit = _build_tree(root)
    if extra_path is not None:
        full = os.path.join(root, *extra_path.split("/"))
        _write(full, b"synthetic non-ASCII artifact\n")
        _git(root, "add", "-A")
        _git(root, "commit", "-q", "-m", "add the non-ASCII tracked file")
    man_path = os.path.join(root, "tests", "golden_manifest.json")
    manifest = _manifest(commit)
    if manifest_mutator is not None:
        manifest_mutator(manifest, commit)
    with open(man_path, "w", encoding="utf8") as f:
        json.dump(manifest, f, indent=2)
    return tmp, _run_lint(root, man_path, force_cp1252, force_cp1252_stdout)


def _register_non_ascii_slot(manifest: dict, commit: str, path: str) -> None:
    """Register `path` (a non-ASCII name) with a WRONG sha: the record's
    `files` slot then names the non-ASCII path, so rule 2 fires and the
    violation message PRINTS that path."""
    capture = ("capture: synthetic capture source@%s (no in-repo writer) - "
               'tests/test_x.cpp "%s"' % (commit, ANCHOR))
    manifest["in_test"].append({
        "test": "synthetic golden case (tests/test_x.cpp, [x] "
                "'synthetic case name')",
        "kind": "in_test",
        "commit": commit + " synthetic tree",
        "produced_by": capture,
        "files": {path: "0" * 64},
    })


class NonAsciiTrackedPathTest(unittest.TestCase):
    """(1) the lint must survive a tracked NON-ASCII name."""

    def test_non_ascii_tracked_name_does_not_crash_the_lint(self):
        tmp, proc = _lint_tree(extra_path=NON_ASCII_NAME)
        with tmp:
            self.assertNotIn("Traceback", proc.stderr,
                             "the lint must not crash: %s" % proc.stderr[-800:])
            self.assertNotIn("AttributeError", proc.stdout + proc.stderr)
            self.assertEqual(
                proc.returncode, 0,
                "the lint must pass on the synthetic tree: %s"
                % proc.stdout[-2000:])

    def test_unregistered_non_ascii_artifact_reports_the_coverage_rule(self):
        # Under tests/fixtures/** the file is an ARTIFACT: the coverage rule
        # flags it as unregistered. That is a normal verdict (exit 1 by the
        # rules) - the point is that there is NO traceback.
        tmp, proc = _lint_tree(
            extra_path="tests/fixtures/" + NON_ASCII_NAME)
        with tmp:
            self.assertNotIn("Traceback", proc.stderr,
                             "the lint must not crash: %s" % proc.stderr[-800:])
            self.assertNotIn("AttributeError", proc.stdout + proc.stderr)
            self.assertEqual(proc.returncode, 1)
            self.assertIn("rule4", proc.stdout)

    def test_lint_works_with_the_locale_forced_to_cp1252(self):
        # (3) the runner's condition: the lint process itself decodes with
        # cp1252. It must still report a normal verdict.
        tmp = tempfile.TemporaryDirectory()
        root = tmp.name
        with tmp:
            commit = _build_tree(root)
            _write(os.path.join(root, NON_ASCII_NAME), b"notes\n")
            _git(root, "add", "-A")
            _git(root, "commit", "-q", "-m", "add the non-ASCII file")
            man_path = os.path.join(root, "tests", "golden_manifest.json")
            with open(man_path, "w", encoding="utf8") as f:
                json.dump(_manifest(commit), f, indent=2)
            proc = _run_lint(root, man_path, force_cp1252=True)
            self.assertNotIn("Traceback", proc.stderr,
                             "the lint must not crash: %s" % proc.stderr[-800:])
            self.assertNotIn("AttributeError", proc.stdout + proc.stderr)
            self.assertEqual(
                proc.returncode, 0,
                "the lint must pass under a forced cp1252 locale: %s"
                % proc.stdout[-2000:])


class NonAsciiStdoutEncodingTest(unittest.TestCase):
    """The OUTPUT dimension: the lint's own PRINTS must never raise. Every
    case forces the child's CONSOLE ENCODING to cp1252 with the STRICT
    error handler (the runner's condition, via PYTHONIOENCODING). Before
    the fix the lint died with a UnicodeEncodeError traceback instead of
    reporting its verdict."""

    def _assert_a_normal_verdict(self, proc):
        self.assertNotIn("Traceback", proc.stdout + proc.stderr,
                         "the lint must not crash: %s"
                         % (proc.stderr[-800:] or proc.stdout[-800:]))
        self.assertNotIn("UnicodeEncodeError", proc.stdout + proc.stderr)

    def test_the_tracked_name_case_prints_a_normal_verdict(self):
        # The non-ASCII name is TRACKED at the repo root: no rule fires on
        # it, so the verdict is PASS (exit 0).
        tmp, proc = _lint_tree(extra_path=NON_ASCII_NAME,
                               force_cp1252_stdout=True)
        with tmp:
            self._assert_a_normal_verdict(proc)
            self.assertEqual(
                proc.returncode, 0,
                "the lint must pass under a cp1252 console: %s"
                % proc.stdout[-2000:])
            self.assertIn("lint_golden_manifest: PASS", proc.stdout)

    def test_the_coverage_rule_case_prints_a_normal_verdict(self):
        # The artifact under tests/fixtures/ is UNREGISTERED: the coverage
        # rule (rule4) flags it - a NORMAL verdict (exit 1 by the rules).
        # This is the case the CI runner failed on.
        tmp, proc = _lint_tree(extra_path="tests/fixtures/" + NON_ASCII_NAME,
                               force_cp1252_stdout=True)
        with tmp:
            self._assert_a_normal_verdict(proc)
            self.assertEqual(
                proc.returncode, 1,
                "the coverage rule must fail the lint: %s" % proc.stdout[-2000:])
            self.assertIn("rule4", proc.stdout)
            # the hardening must not swallow the message: the escaped path
            # is still IN the output (the reader sees WHICH path failed)
            self.assertIn("\\u043c", proc.stdout,
                          "the non-ASCII path must be escaped, not dropped")

    def test_the_registered_slot_case_prints_a_normal_verdict(self):
        # The non-ASCII path is REGISTERED (a registry slot) with a wrong
        # sha: rule 2 fires and the message PRINTS that path.
        tmp, proc = _lint_tree(
            extra_path=NON_ASCII_NAME,
            force_cp1252_stdout=True,
            manifest_mutator=lambda man, commit: _register_non_ascii_slot(
                man, commit, NON_ASCII_NAME))
        with tmp:
            self._assert_a_normal_verdict(proc)
            self.assertEqual(
                proc.returncode, 1,
                "the sha rule must fail the lint: %s" % proc.stdout[-2000:])
            self.assertIn("rule2", proc.stdout)


class ForcedLocalePremiseTest(unittest.TestCase):
    """The premise of the regression, proved in a child process: under a
    forced cp1252 locale a LOCALE-decoded capture loses the text (the CI
    crash), while an EXPLICITLY decoded capture keeps it."""

    def _probe(self) -> dict:
        with tempfile.TemporaryDirectory() as tmp:
            script = os.path.join(tmp, "probe.py")
            with open(script, "w", encoding="utf8") as f:
                f.write(_DECODE_PROBE)
            proc = subprocess.run([sys.executable, script],
                                  capture_output=True, cwd=REPO_ROOT,
                                  encoding="utf-8", errors="surrogateescape")
            self.assertEqual(proc.returncode, 0, proc.stderr[-800:])
            out = {}
            for line in proc.stdout.splitlines():
                key, _, value = line.partition(" ")
                out[key] = value
            return out

    def test_the_forced_locale_breaks_a_locale_decoded_capture(self):
        out = self._probe()
        # ascii() keeps the probe's own output ASCII, so the assertion
        # below sees the CODE POINTS, not the console's rendering of them.
        self.assertNotIn("\\u044f", out.get("LOCALE", ""),
                         "a locale-decoded capture must NOT keep the text "
                         "under a forced cp1252 locale - that is the CI bug")
        self.assertIn("\\u044f", out.get("EXPLICIT", ""),
                      "an explicitly decoded capture must keep the text "
                      "under a forced cp1252 locale")


class SubprocessEncodingGuardTest(unittest.TestCase):
    """(4) the class of bug must not come back: every locale-decoded
    subprocess capture names an explicit encoding.

    The scan itself lives in tools/lint_locale_independence.py (the CI
    runs that script as a blocking gate); this test calls it, so the
    rule is proven ONCE.
    """

    def _violations(self):
        violations, _notes = LOCALE.evaluate(REPO_ROOT)
        return violations

    def test_no_tool_decodes_a_subprocess_with_the_locale(self):
        violations = self._violations()
        self.assertEqual(
            violations, [],
            "a locale-decoded subprocess capture must name an explicit "
            "encoding (encoding=\"utf-8\", errors=\"surrogateescape\"):\n"
            + "\n".join(violations))

    def test_the_guard_script_flags_a_locale_decoded_capture(self):
        # The guard must actually FIRE (a guard that cannot fail proves
        # nothing): a synthetic tool with text=True and no encoding= is
        # a violation, and the same file with an explicit encoding= is
        # clean.
        bad = ("import subprocess\n"
               "def run(cmd):\n"
               "    return subprocess.run(cmd, capture_output=True, "
               "text=True)\n")
        good = ("import subprocess\n"
                "def run(cmd):\n"
                "    return subprocess.run(cmd, capture_output=True, "
                "text=True, encoding=\"utf-8\", errors=\"surrogateescape\")\n")
        bad_hits = LOCALE.scan_source(bad, "synthetic_bad.py",
                                      "synthetic_bad.py")
        self.assertEqual(len(bad_hits), 1, bad_hits)
        self.assertIn("decodes with the LOCALE", bad_hits[0])
        good_hits = LOCALE.scan_source(good, "synthetic_good.py",
                                       "synthetic_good.py")
        self.assertEqual(good_hits, [], good_hits)


if __name__ == "__main__":
    unittest.main(verbosity=2)
