import io
import os
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

PKG = Path(__file__).parent.parent / "shalias"


def _capture(fn, *a, **kw):
    """Run *fn* and hand back whatever it printed."""
    buf = io.StringIO()
    with patch("sys.stdout", buf):
        fn(*a, **kw)
    return buf.getvalue()


# ── update ────────────────────────────────────────────────────────────────────

class TestInstallMode(unittest.TestCase):

    def test_a_checkout_is_source(self):
        from shalias.commands.io_ops import install_mode
        # The tests run from the repo, so pyproject.toml is right there.
        self.assertEqual(install_mode(), "source")

    def test_pipx_venv_is_pipx(self):
        from shalias.commands import io_ops
        fake = str(Path.home() / ".local" / "pipx" / "venvs" / "shalias")
        with patch.object(io_ops.Path, "exists", lambda self: False), \
             patch("sys.prefix", fake):
            self.assertEqual(io_ops.install_mode(), "pipx")


class TestCmdUpdate(unittest.TestCase):

    def test_source_checkout_is_left_alone(self):
        from shalias.commands import io_ops
        with patch("shalias.commands.io_ops.subprocess.run") as run:
            out = _capture(io_ops.cmd_update, types.SimpleNamespace())
        run.assert_not_called()
        self.assertIn("git pull", out)

    def test_pip_install_shells_out_to_pip(self):
        from shalias.commands import io_ops
        with patch("shalias.commands.io_ops.install_mode", return_value="pip"), \
             patch("shalias.commands.io_ops.subprocess.run") as run:
            run.return_value = types.SimpleNamespace(returncode=0)
            _capture(io_ops.cmd_update, types.SimpleNamespace())
        cmd = run.call_args[0][0]
        self.assertEqual(cmd[0], sys.executable)
        self.assertEqual(cmd[1:], ["-m", "pip", "install", "--upgrade", "shalias"])

    def test_pipx_install_shells_out_to_pipx(self):
        from shalias.commands import io_ops
        with patch("shalias.commands.io_ops.install_mode", return_value="pipx"), \
             patch("shalias.commands.io_ops.subprocess.run") as run:
            run.return_value = types.SimpleNamespace(returncode=0)
            _capture(io_ops.cmd_update, types.SimpleNamespace())
        self.assertEqual(run.call_args[0][0], ["pipx", "upgrade", "shalias"])

    def test_a_failed_upgrade_exits_nonzero(self):
        from shalias.commands import io_ops
        with patch("shalias.commands.io_ops.install_mode", return_value="pip"), \
             patch("shalias.commands.io_ops.subprocess.run") as run:
            run.return_value = types.SimpleNamespace(returncode=1)
            with self.assertRaises(SystemExit):
                _capture(io_ops.cmd_update, types.SimpleNamespace())

    def test_missing_pipx_tells_you_the_command(self):
        from shalias.commands import io_ops
        with patch("shalias.commands.io_ops.install_mode", return_value="pipx"), \
             patch("shalias.commands.io_ops.subprocess.run", side_effect=OSError("nope")):
            with self.assertRaises(SystemExit):
                out = _capture(io_ops.cmd_update, types.SimpleNamespace())


class TestNoNetworkCalls(unittest.TestCase):
    """
    shalias used to poll GitHub on every `list` and `add`. Nothing in the
    package should open a socket now - updates go through pip, on request.
    """

    def test_nothing_in_the_package_opens_a_url(self):
        offenders = [
            p.relative_to(PKG).as_posix()
            for p in PKG.rglob("*.py")
            if "urlopen" in p.read_text(encoding="utf-8")
        ]
        self.assertEqual(offenders, [])

    def test_the_background_version_check_is_gone(self):
        import shalias.utils as utils
        self.assertFalse(hasattr(utils, "check_update_async"))


if __name__ == "__main__":
    unittest.main()
