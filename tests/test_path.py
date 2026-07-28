import io
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))


def _capture(fn, *a, **kw):
    """Run *fn* and hand back whatever it printed."""
    buf = io.StringIO()
    with patch("sys.stdout", buf):
        fn(*a, **kw)
    return buf.getvalue()


# ── PATH diagnostics ──────────────────────────────────────────────────────────

class TestPathChecks(unittest.TestCase):

    def setUp(self):
        from shalias import path_manager
        self.pm  = path_manager
        self.bin = Path.home() / ".shalias" / "bin"

    def _with_path(self, value):
        return patch.dict(os.environ, {"PATH": value})

    def test_active_when_on_the_path(self):
        with self._with_path(os.pathsep.join(["/usr/bin", str(self.bin)])):
            self.assertTrue(self.pm.path_is_active())

    def test_not_active_when_absent(self):
        with self._with_path("/usr/bin"):
            self.assertFalse(self.pm.path_is_active())

    def test_trailing_separator_still_counts(self):
        with self._with_path(str(self.bin) + os.sep):
            self.assertTrue(self.pm.path_is_active())

    def test_a_similar_looking_directory_does_not_count(self):
        with self._with_path(str(self.bin) + "2"):
            self.assertFalse(self.pm.path_is_active())


class TestDoctorPathAdvice(unittest.TestCase):

    def test_says_nothing_when_the_path_is_fine(self):
        from shalias.commands import run_ops
        with patch("shalias.commands.run_ops.path_is_active", return_value=True):
            self.assertEqual(_capture(run_ops.check_path), "")

    def test_tells_you_to_install_when_the_path_was_never_set(self):
        from shalias.commands import run_ops
        with patch("shalias.commands.run_ops.path_is_active",    return_value=False), \
             patch("shalias.commands.run_ops.path_is_persisted", return_value=False):
            out = _capture(run_ops.check_path)
        self.assertIn("shalias install", out)

    def test_hands_you_the_one_liner_when_the_shell_is_just_stale(self):
        from shalias.commands import run_ops
        from shalias.path_manager import activate_hint
        with patch("shalias.commands.run_ops.path_is_active",    return_value=False), \
             patch("shalias.commands.run_ops.path_is_persisted", return_value=True):
            out = _capture(run_ops.check_path)
        self.assertIn(activate_hint(), out)
        self.assertNotIn("shalias install", out)


if __name__ == "__main__":
    unittest.main()
