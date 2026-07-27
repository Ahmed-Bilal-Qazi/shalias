import sys
import unittest
from pathlib import Path
from unittest.mock import patch
import tempfile

sys.path.insert(0, str(Path(__file__).parent.parent))

UNIX = sys.platform != "win32"


class TestLauncher(unittest.TestCase):

    def setUp(self):
        self._td  = tempfile.TemporaryDirectory()
        self.bin  = Path(self._td.name) / "bin"
        self.bin.mkdir()

    def tearDown(self):
        self._td.cleanup()

    def _write(self, alias, entry):
        with patch("shalias.launcher.BIN_DIR", self.bin):
            from shalias.launcher import write_launcher
            return write_launcher(alias, entry)

    @unittest.skipUnless(UNIX, "Unix only")
    def test_run_launcher_created(self):
        entry = {"type": "run", "script": "/home/user/app.py",
                 "interpreter": "python3", "env": {}, "cwd": ""}
        launcher = self._write("myapp", entry)
        self.assertTrue(launcher.exists())
        content = launcher.read_text()
        self.assertIn("python3",        content)
        self.assertIn("/home/user/app.py", content)

    @unittest.skipUnless(UNIX, "Unix only")
    def test_launcher_is_executable(self):
        entry = {"type": "run", "script": "/tmp/x.py",
                 "interpreter": "python3", "env": {}, "cwd": ""}
        launcher = self._write("x", entry)
        self.assertTrue(launcher.stat().st_mode & 0o111)

    @unittest.skipUnless(UNIX, "Unix only")
    def test_env_vars_baked_in(self):
        entry = {"type": "run", "script": "/tmp/s.py",
                 "interpreter": "python3",
                 "env": {"PORT": "8080", "DEBUG": "true"}, "cwd": ""}
        launcher = self._write("srv", entry)
        content = launcher.read_text()
        self.assertIn('export PORT="8080"',  content)
        self.assertIn('export DEBUG="true"', content)

    @unittest.skipUnless(UNIX, "Unix only")
    def test_inline_launcher(self):
        entry = {"type": "inline", "target": "git status && git log --oneline",
                 "env": {}, "cwd": ""}
        launcher = self._write("gst", entry)
        self.assertIn("git status", launcher.read_text())

    @unittest.skipUnless(UNIX, "Unix only")
    def test_chain_launcher(self):
        entry = {"type": "chain", "chain": ["test", "build", "deploy"],
                 "env": {}, "cwd": ""}
        launcher = self._write("release", entry)
        content = launcher.read_text()
        for step in ("test", "build", "deploy"):
            self.assertIn(step, content)

    @unittest.skipUnless(UNIX, "Unix only")
    def test_remove_launcher(self):
        entry = {"type": "run", "script": "/tmp/a.py",
                 "interpreter": "python3", "env": {}, "cwd": ""}
        self._write("gone", entry)
        self.assertTrue((self.bin / "gone").exists())
        with patch("shalias.launcher.BIN_DIR", self.bin):
            from shalias.launcher import remove_launcher
            remove_launcher("gone")
        self.assertFalse((self.bin / "gone").exists())

    @unittest.skipUnless(UNIX, "Unix only")
    def test_unknown_type_raises(self):
        entry = {"type": "bogus", "env": {}, "cwd": ""}
        with self.assertRaises(ValueError):
            self._write("bad", entry)


if __name__ == "__main__":
    unittest.main()
