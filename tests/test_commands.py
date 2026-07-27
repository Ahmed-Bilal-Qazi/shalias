import io
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

UNIX = sys.platform != "win32"


def _ns(**kw):
    """Minimal argparse namespace with sane defaults."""
    defaults = dict(
        alias=None, script=None, type=None, interpreter=None,
        inline=False, cwd=None, env=None, group=None, description=None,
        format="table", json=False, sort=None, check=False, pattern=None,
        aliases=[], parallel=False, fix=False, dry_run=False, chain=None,
    )
    defaults.update(kw)
    return types.SimpleNamespace(**defaults)


def _edit_ns(alias, **kw):
    """Namespace shaped like `shalias edit` - every flag present, all off."""
    defaults = dict(
        alias=alias, new_alias=None, script=None, type=None, interpreter=None,
        cwd=None, env=None, description=None, group=None,
        lock=False, unlock=False, enable=False, disable=False,
    )
    defaults.update(kw)
    return types.SimpleNamespace(**defaults)


class _EnvMixin:
    """Sets up an isolated temp filesystem for each test via context manager patches."""

    def setUp(self):
        self._td        = tempfile.TemporaryDirectory()
        td              = Path(self._td.name)
        self.cfg_file   = td / "config.json"
        self.bin_dir    = td / "bin"
        self.backup_dir = td / "backups"
        self.td         = td
        self.bin_dir.mkdir()
        self.cfg_file.write_text(
            json.dumps({"aliases": {}, "groups": {}, "meta": {}}), encoding="utf-8"
        )
        # Use context-manager style so patches are definitely active during the test body
        self._cm = self._apply_patches()
        self._cm.__enter__()

    def _apply_patches(self):
        import contextlib
        @contextlib.contextmanager
        def _ctx():
            with patch("shalias.config.CONFIG_FILE",       self.cfg_file), \
                 patch("shalias.config.SHALIAS_DIR",       self.td), \
                 patch("shalias.config.BACKUP_DIR",        self.backup_dir), \
                 patch("shalias.launcher.BIN_DIR",         self.bin_dir), \
                 patch("shalias.constants.BIN_DIR",        self.bin_dir), \
                 patch("shalias.commands.run_ops.BIN_DIR", self.bin_dir):
                yield
        return _ctx()

    def tearDown(self):
        self._cm.__exit__(None, None, None)
        self._td.cleanup()

    def load(self):
        from shalias.config import load_config
        return load_config()

    def save(self, cfg):
        from shalias.config import save_config
        save_config(cfg)

    def _make_script(self, name="script.py", content=""):
        p = self.td / name
        p.write_text(content)
        return p


# ── add ───────────────────────────────────────────────────────────────────────

class TestCmdAdd(_EnvMixin, unittest.TestCase):

    @unittest.skipUnless(UNIX, "Unix only")
    def test_add_creates_entry_and_launcher(self):
        script = self._make_script("hello.py", "print('hi')")
        from shalias.commands.alias_ops import cmd_add
        cmd_add(_ns(script=str(script), alias="hello"))
        cfg = self.load()
        self.assertIn("hello", cfg["aliases"])
        self.assertEqual(cfg["aliases"]["hello"]["type"], "run")
        self.assertTrue((self.bin_dir / "hello").exists())

    @unittest.skipUnless(UNIX, "Unix only")
    def test_add_url(self):
        from shalias.commands.alias_ops import cmd_add
        cmd_add(_ns(script="https://github.com", alias="gh", type="url"))
        self.assertEqual(self.load()["aliases"]["gh"]["type"], "url")

    def test_add_duplicate_exits(self):
        script = self._make_script("app.py")
        cfg = self.load()
        cfg["aliases"]["myapp"] = {"type": "run", "script": str(script)}
        self.save(cfg)
        from shalias.commands.alias_ops import cmd_add
        with self.assertRaises(SystemExit):
            cmd_add(_ns(script=str(script), alias="myapp"))

    def test_add_missing_file_exits(self):
        from shalias.commands.alias_ops import cmd_add
        with self.assertRaises(SystemExit):
            cmd_add(_ns(script=str(self.td / "nope.py"), alias="bad"))


# ── remove ────────────────────────────────────────────────────────────────────

class TestCmdRemove(_EnvMixin, unittest.TestCase):

    @unittest.skipUnless(UNIX, "Unix only")
    def test_remove(self):
        script = self._make_script("bye.py")
        from shalias.commands.alias_ops import cmd_add, cmd_remove
        cmd_add(_ns(script=str(script), alias="bye"))
        cmd_remove(_ns(alias="bye"))
        cfg = self.load()
        self.assertNotIn("bye", cfg["aliases"])
        self.assertFalse((self.bin_dir / "bye").exists())

    def test_remove_locked_exits(self):
        cfg = self.load()
        cfg["aliases"]["locked"] = {"type": "run", "locked": True, "script": "/x"}
        self.save(cfg)
        from shalias.commands.alias_ops import cmd_remove
        with self.assertRaises(SystemExit):
            cmd_remove(_ns(alias="locked"))


# ── rename ────────────────────────────────────────────────────────────────────

class TestCmdRename(_EnvMixin, unittest.TestCase):

    @unittest.skipUnless(UNIX, "Unix only")
    def test_rename(self):
        # Populate config directly to avoid cross-test patch interference
        script = self._make_script("orig.py")
        cfg = self.load()
        cfg["aliases"]["orig"] = {
            "type": "run", "script": str(script),
            "interpreter": "python3", "env": {}, "cwd": "",
        }
        self.save(cfg)
        # Create the launcher so remove_launcher has something to remove
        from shalias.launcher import write_launcher
        write_launcher("orig", cfg["aliases"]["orig"])

        from shalias.commands.edit import cmd_edit
        cmd_edit(_edit_ns("orig", new_alias="renamed"))

        cfg = self.load()
        self.assertNotIn("orig",    cfg["aliases"])
        self.assertIn("renamed",    cfg["aliases"])
        self.assertFalse((self.bin_dir / "orig").exists())
        self.assertTrue((self.bin_dir  / "renamed").exists())


# ── edit --lock / --enable ────────────────────────────────────────────────────

class TestLockAndEnable(_EnvMixin, unittest.TestCase):

    def _seed(self, name="x"):
        cfg = self.load()
        cfg["aliases"][name] = {"type": "inline", "target": "echo hi",
                                "env": {}, "cwd": ""}
        self.save(cfg)

    def test_lock_then_unlock(self):
        from shalias.commands.edit import cmd_edit
        self._seed()
        cmd_edit(_edit_ns("x", lock=True))
        self.assertTrue(self.load()["aliases"]["x"]["locked"])
        cmd_edit(_edit_ns("x", unlock=True))
        self.assertFalse(self.load()["aliases"]["x"]["locked"])

    def test_locked_alias_refuses_edits(self):
        from shalias.commands.edit import cmd_edit
        self._seed()
        cmd_edit(_edit_ns("x", lock=True))
        with self.assertRaises(SystemExit):
            cmd_edit(_edit_ns("x", description="nope"))

    def test_disable_then_enable(self):
        from shalias.commands.edit import cmd_edit
        self._seed()
        cmd_edit(_edit_ns("x", disable=True))
        self.assertFalse(self.load()["aliases"]["x"]["enabled"])
        cmd_edit(_edit_ns("x", enable=True))
        self.assertTrue(self.load()["aliases"]["x"]["enabled"])

    def test_lock_and_unlock_together_is_rejected(self):
        from shalias.commands.edit import cmd_edit
        self._seed()
        with self.assertRaises(SystemExit):
            cmd_edit(_edit_ns("x", lock=True, unlock=True))

    def test_disable_parks_the_launcher(self):
        from shalias.commands.edit import cmd_edit
        from shalias.launcher import write_launcher
        self._seed()
        write_launcher("x", self.load()["aliases"]["x"])
        live = self.bin_dir / ("x.bat" if not UNIX else "x")
        parked = live.with_name(live.name + ".disabled")

        cmd_edit(_edit_ns("x", disable=True))
        self.assertFalse(live.exists())
        self.assertTrue(parked.exists())

        cmd_edit(_edit_ns("x", enable=True))
        self.assertTrue(live.exists())
        self.assertFalse(parked.exists())

    def test_remove_cleans_up_a_disabled_launcher(self):
        from shalias.commands.alias_ops import cmd_remove
        from shalias.commands.edit import cmd_edit
        from shalias.launcher import write_launcher
        self._seed()
        write_launcher("x", self.load()["aliases"]["x"])
        cmd_edit(_edit_ns("x", disable=True))
        cmd_remove(_ns(alias="x"))
        self.assertEqual(list(self.bin_dir.glob("x*")), [])


# ── chain ─────────────────────────────────────────────────────────────────────

class TestCmdChain(_EnvMixin, unittest.TestCase):

    @unittest.skipUnless(UNIX, "Unix only")
    def test_chain(self):
        cfg = self.load()
        cfg["aliases"]["a"] = {"type": "inline", "target": "echo a", "env": {}, "cwd": ""}
        cfg["aliases"]["b"] = {"type": "inline", "target": "echo b", "env": {}, "cwd": ""}
        self.save(cfg)
        from shalias.commands.alias_ops import cmd_chain
        cmd_chain(types.SimpleNamespace(
            name="ab", run=["a", "b"], group=None, description=None
        ))
        cfg = self.load()
        self.assertEqual(cfg["aliases"]["ab"]["type"],  "chain")
        self.assertEqual(cfg["aliases"]["ab"]["chain"], ["a", "b"])


# ── stats --format ────────────────────────────────────────────────────────────

# ── list --type filter ────────────────────────────────────────────────────────

class TestListTypeFilter(_EnvMixin, unittest.TestCase):

    def test_filters_by_type(self):
        cfg = self.load()
        cfg["aliases"]["myscript"] = {"type": "run",  "script": "/tmp/x.py"}
        cfg["aliases"]["myurl"]    = {"type": "url",  "target": "https://ex.com"}
        self.save(cfg)
        captured = io.StringIO()
        from shalias.commands.list_search import cmd_list
        with patch("sys.stdout", captured):
            cmd_list(_ns(type="url", group=None, sort=None, check=False, format="plain"))
        out = captured.getvalue()
        self.assertIn("myurl",       out)
        self.assertNotIn("myscript", out)


# ── rename-cmd ────────────────────────────────────────────────────────────────

class TestRenameCmd(_EnvMixin, unittest.TestCase):

    @unittest.skipUnless(UNIX, "Unix only")
    def test_rename_cmd_stores_name(self):
        from shalias.commands.io_ops import cmd_rename_cmd
        cmd_rename_cmd(types.SimpleNamespace(name="sa"))
        cfg = self.load()
        self.assertEqual(cfg["meta"]["command_name"], "sa")
        self.assertTrue((self.bin_dir / "sa").exists())

    def test_rename_cmd_invalid_name(self):
        from shalias.commands.io_ops import cmd_rename_cmd
        with self.assertRaises(SystemExit):
            cmd_rename_cmd(types.SimpleNamespace(name="my cmd"))


# ── export / import ───────────────────────────────────────────────────────────

class TestExportImport(_EnvMixin, unittest.TestCase):

    def test_roundtrip(self):
        cfg = self.load()
        cfg["aliases"]["x"] = {
            "type": "inline", "target": "echo x",
             "env": {}, "cwd": "",
        }
        self.save(cfg)
        backup = self.td / "backup.json"
        from shalias.commands.io_ops import cmd_export, cmd_import
        cmd_export(types.SimpleNamespace(output=str(backup)))
        self.assertTrue(backup.exists())
        # Clear aliases then reimport
        cfg["aliases"] = {}
        self.save(cfg)
        cmd_import(types.SimpleNamespace(input=str(backup), dry_run=False))
        self.assertIn("x", self.load()["aliases"])

    def test_dry_run_does_not_apply(self):
        backup = self.td / "b.json"
        backup.write_text(json.dumps({"aliases": {
            "drytest": {"type": "inline", "target": "echo"}
        }}), encoding="utf-8")
        from shalias.commands.io_ops import cmd_import
        cmd_import(types.SimpleNamespace(input=str(backup), dry_run=True))
        self.assertNotIn("drytest", self.load()["aliases"])


if __name__ == "__main__":
    unittest.main()
