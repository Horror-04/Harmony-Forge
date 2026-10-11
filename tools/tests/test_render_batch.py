"""Self-test for tools/render_batch.py (Phase 2 Task 2, stdlib unittest only).

Run: python tools/tests/test_render_batch.py   (from repo root)
"""
import hashlib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT = REPO_ROOT / "tools" / "render_batch.py"


def run_batch(*args):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
    )


class RenderBatchTest(unittest.TestCase):
    def test_batch_twice_identical_bytes_and_sidecars(self):
        with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
            for d in (d1, d2):
                r = run_batch("--seeds", "7,8", "--bars", "4", "--out", d)
                self.assertEqual(r.returncode, 0, msg=r.stderr)
            for seed in (7, 8):
                f1 = Path(d1) / f"{seed}-4.mid"
                f2 = Path(d2) / f"{seed}-4.mid"
                self.assertTrue(f1.is_file(), msg=f"missing {f1}")
                self.assertTrue(f2.is_file(), msg=f"missing {f2}")
                b1, b2 = f1.read_bytes(), f2.read_bytes()
                self.assertGreater(len(b1), 0)
                self.assertEqual(b1, b2, msg=f"seed {seed} not deterministic")
                for f, d in ((f1, d1), (f2, d2)):
                    sidecar = Path(d) / f"{seed}-4.mid.sha256"
                    self.assertTrue(sidecar.is_file(), msg=f"missing {sidecar}")
                    expected = hashlib.sha256(f.read_bytes()).hexdigest()
                    self.assertEqual(sidecar.read_text().strip(), expected)

    def test_bad_seed_exits_nonzero(self):
        with tempfile.TemporaryDirectory() as d:
            r = run_batch("--seeds", "abc", "--bars", "4", "--out", d)
            self.assertNotEqual(r.returncode, 0)


if __name__ == "__main__":
    unittest.main()
