# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""CI-safe console output: a tool's PRINTS must never raise.

THE FAILURE THIS PREVENTS (the repository's SECOND GitHub Actions run, the
gates job's new "Python gate tests" step)::

    FAILED tools/tests/test_git_locale_independence.py::NonAsciiTrackedPathTest::
      test_unregistered_non_ascii_artifact_reports_the_coverage_rule
      AssertionError: 'Traceback' unexpectedly found in '...
        File "tools/lint_golden_manifest.py", line 833, in main
          print(f"lint_golden_manifest: FAIL: {msg}")
        File ".../encodings/cp1252.py", line 19, in encode
          UnicodeEncodeError: 'charmap' codec can't encode characters in position 49-59'

ROOT CAUSE: the previous wave fixed the tools' INPUT side (every captured
subprocess decodes EXPLICITLY - see tools/lint_locale_independence.py). The
OUTPUT side still went through the LOCALE: ``print()`` of a violation
message that contains a non-ASCII path raises UnicodeEncodeError on a cp1252
console, so the lint died with a traceback INSTEAD of reporting its verdict.
The regression test of that wave passed locally only because the local
console is cp1251 (which CAN encode those characters): it forced the LOCALE
(for the subprocess decode) but never the STDOUT ENCODING (for the print) -
so the CI runner (whose console is the cp1252 ANSI code page) caught it on
its first execution.

THE APPROACH (ONE implementation, used by every tool - no copy-paste):

    ci_encoding.harden_console()

reconfigures ``sys.stdout`` and ``sys.stderr`` with an error handler that
REPLACES the unencodable characters instead of raising, and KEEPS each
stream's own encoding:

  * the ENCODING is never changed - the console's own code page stays in
    force, so the rest of the output (the verdict lines, the rule tags, the
    counters) stays exactly as readable as it was;
  * the ERROR HANDLER changes from "strict" to "backslashreplace": a
    character the console cannot represent is written as its escape
    (``\\u043c``) instead of raising UnicodeEncodeError. The verdict line and
    the exit code are therefore ALWAYS produced - a gate that dies with a
    traceback reports NOTHING, which is the worst possible failure mode
    for a blocking gate;
  * "backslashreplace" (not "replace") is deliberate: the offending text
    stays visible as an escape sequence, so the reader can still see WHICH
    path was offending; "replace" would silently turn it into "?".

FALLBACK: a stream that refuses ``reconfigure()`` is wrapped in a proxy
that encodes defensively. The helper NEVER raises: hardening the console
must not be the thing that breaks a tool.

Both usages share this one helper - the tool as a SCRIPT
(``python tools/<tool>.py``, where sys.path[0] IS tools/) and the tool
IMPORTED by a test (the repo's tools/tests/ insert tools/ on sys.path
before importing a tool module).

Usage (in every tool that prints user-controlled text - a path, a file
name, a rule message - BEFORE its first print)::

    import ci_encoding
    ...
    def main(...) -> int:
        ci_encoding.harden_console()
        ...
"""

from __future__ import annotations

import sys

# The error handler the console streams get (see the module docstring).
ERROR_HANDLER = "backslashreplace"


class SafeStream:
    """A text stream whose ``write`` never raises UnicodeEncodeError.

    The fallback for a stream that refuses ``reconfigure()``. The text is
    encoded with the stream's own encoding and "backslashreplace", so an
    unencodable character becomes its escape instead of an exception.
    """

    __slots__ = ("_stream", "_encoding")

    def __init__(self, stream):
        self._stream = stream
        encoding = getattr(stream, "encoding", None)
        self._encoding = encoding if isinstance(encoding, str) and encoding \
            else "ascii"

    def write(self, text):
        try:
            return self._stream.write(text)
        except UnicodeEncodeError:
            safe = text.encode(self._encoding, ERROR_HANDLER)
            return self._stream.write(safe.decode(self._encoding))

    def flush(self):
        return self._stream.flush()

    def __getattr__(self, name):
        # Only reached for attributes the wrapper does not define itself.
        if name.startswith("_"):
            raise AttributeError(name)
        return getattr(self._stream, name)


def harden_stream(stream):
    """Return ``(stream, note)``: a stream that cannot raise on an
    unencodable character, plus a one-line note of what was done.

    The stream's OWN encoding is kept; only its error handler changes.
    """
    if stream is None:
        return None, "no stream"
    if isinstance(stream, SafeStream):
        return stream, "already hardened (proxy)"
    if getattr(stream, "errors", None) == ERROR_HANDLER:
        return stream, "already hardened (errors=%s)" % ERROR_HANDLER
    reconfigure = getattr(stream, "reconfigure", None)
    if callable(reconfigure):
        try:
            reconfigure(errors=ERROR_HANDLER)
        except Exception:       # noqa: BLE001 - any refusal falls back
            pass
        else:
            return stream, ("reconfigured: errors=%s, encoding kept (%s)"
                            % (ERROR_HANDLER, getattr(stream, "encoding", None)))
    if hasattr(stream, "write"):
        return SafeStream(stream), ("wrapped: the stream refused "
                                     "reconfigure(errors=...)")
    return stream, "skipped: the stream has no write()"


def harden_console():
    """Harden ``sys.stdout`` and ``sys.stderr``. Returns the notes.

    It PRINTS NOTHING (a gate's output is asserted by the tests) and it
    NEVER raises: hardening the console must not be the thing that breaks
    a tool. Call it once, before the first print.
    """
    notes = []
    for name in ("stdout", "stderr"):
        stream = getattr(sys, name, None)
        safe, note = harden_stream(stream)
        if safe is not stream:
            setattr(sys, name, safe)
        notes.append("%s: %s" % (name, note))
    return notes


def safe_text(text, encoding=None):
    """`text` with every character `encoding` cannot represent replaced by
    its escape. Never raises (the tests use it to build the expectation).
    """
    if encoding is None:
        encoding = getattr(sys.stdout, "encoding", None) or "ascii"
    return text.encode(encoding, ERROR_HANDLER).decode(encoding)


if __name__ == "__main__":
    # A tiny self-check: `python tools/ci_encoding.py` prints what the
    # console streams look like after the hardening.
    print("ci_encoding: hardening the console...")
    for note in harden_console():
        print("ci_encoding: %s" % note)
    print("ci_encoding: stdout encoding=%s errors=%s"
          % (sys.stdout.encoding, sys.stdout.errors))
