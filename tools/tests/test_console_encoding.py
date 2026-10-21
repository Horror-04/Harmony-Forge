# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""The console-hardening helper itself (tools/ci_encoding.py).

Split out of tools/tests/test_git_locale_independence.py (that file sat at
the 500-line pin, and the helper is a general OUTPUT guard, not another
locale-decode case). This is the unit-level proof of the helper: a cp1252
console - the windows-2022 runner's condition - must be able to print a
non-ASCII path, ESCAPED, never raised, and the console's own encoding must
be KEPT (the rest of the output stays readable in its code page).

Run: py -3 -m pytest tools/tests/test_console_encoding.py
  (or: py -3 tools/tests/test_console_encoding.py)
"""

import os
import subprocess
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
TOOLS_DIR = os.path.join(REPO_ROOT, "tools")

# The runner's console condition exactly (the CI failure's second run): a
# cp1252 console with the STRICT handler, so an UNhardened print of a
# non-ASCII path RAISES UnicodeEncodeError.
_CP1252_CONSOLE_ENV = {"PYTHONIOENCODING": "cp1252:strict"}

# The tracked name that broke the first CI run (Cyrillic).
NON_ASCII_NAME = "методология.txt"


class ConsoleHardeningTest(unittest.TestCase):
    """The helper itself (tools/ci_encoding.py): a cp1252 console must be
    able to print a non-ASCII path (escaped, never raised)."""

    PROBE = (
        "import sys\n"
        "sys.path.insert(0, %r)\n"
        "import ci_encoding\n"
        "ci_encoding.harden_console()\n"
        "print('ENCODING', sys.stdout.encoding)\n"
        "print('VERDICT:', %r)\n" % (TOOLS_DIR, NON_ASCII_NAME)
    )

    def test_a_cp1252_console_prints_a_non_ascii_path(self):
        env = dict(os.environ)
        env.update(_CP1252_CONSOLE_ENV)
        proc = subprocess.run([sys.executable, "-c", self.PROBE],
                              capture_output=True, cwd=REPO_ROOT, env=env,
                              encoding="utf-8", errors="surrogateescape")
        self.assertEqual(proc.returncode, 0, proc.stderr[-800:])
        self.assertNotIn("Traceback", proc.stderr)
        self.assertNotIn("UnicodeEncodeError", proc.stdout + proc.stderr)
        # the console's own encoding is KEPT (the rest of the output stays
        # readable in the console's code page)
        self.assertIn("ENCODING cp1252", proc.stdout)
        # the unencodable characters are escaped, never raised and never
        # silently dropped
        self.assertIn("VERDICT: ", proc.stdout)
        self.assertIn("\\u043c", proc.stdout)
        self.assertNotIn(NON_ASCII_NAME, proc.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
