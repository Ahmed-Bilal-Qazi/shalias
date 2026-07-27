import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestLoadConfig(unittest.TestCase):

    def test_missing_file_returns_blank(self):
        import tempfile, os
        with tempfile.TemporaryDirectory() as td:
            cfg_file = Path(td) / "config.json"
            with patch("shalias.config.CONFIG_FILE", cfg_file):
                from shalias.config import load_config
                cfg = load_config()
        self.assertEqual(cfg, {"aliases": {}, "groups": {}, "meta": {}})

    def test_sets_missing_defaults(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            cfg_file = Path(td) / "config.json"
            cfg_file.write_text(json.dumps({"aliases": {"x": {}}}))
            with patch("shalias.config.CONFIG_FILE", cfg_file):
                from shalias.config import load_config
                cfg = load_config()
        self.assertIn("groups", cfg)
        self.assertIn("meta", cfg)

    def test_save_and_reload(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            cfg_file    = Path(td) / "config.json"
            shalias_dir = Path(td)
            data = {"aliases": {"a": {"type": "run"}}, "groups": {}, "meta": {}}
            with patch("shalias.config.CONFIG_FILE", cfg_file), \
                 patch("shalias.config.SHALIAS_DIR",  shalias_dir):
                from shalias.config import save_config, load_config
                save_config(data)
                loaded = load_config()
        self.assertEqual(loaded["aliases"]["a"]["type"], "run")

    def test_no_tmp_files_left(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            cfg_file    = Path(td) / "config.json"
            shalias_dir = Path(td)
            with patch("shalias.config.CONFIG_FILE", cfg_file), \
                 patch("shalias.config.SHALIAS_DIR",  shalias_dir):
                from shalias.config import save_config
                save_config({"aliases": {}, "groups": {}, "meta": {}})
            leftovers = list(Path(td).glob("*.tmp"))
        self.assertEqual(leftovers, [])

    def test_backup_keeps_ten(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            cfg_file    = Path(td) / "config.json"
            backup_dir  = Path(td) / "backups"
            shalias_dir = Path(td)
            cfg_file.write_text("{}")
            with patch("shalias.config.CONFIG_FILE", cfg_file), \
                 patch("shalias.config.BACKUP_DIR",  backup_dir), \
                 patch("shalias.config.SHALIAS_DIR", shalias_dir):
                from shalias.config import backup_config
                for _ in range(15):
                    backup_config()
            backups = list(backup_dir.glob("config_*.json"))
        self.assertLessEqual(len(backups), 10)

    def test_get_command_name_default(self):
        from shalias.config import get_command_name
        self.assertEqual(get_command_name({}), "shalias")
        self.assertEqual(get_command_name({"meta": {}}), "shalias")

    def test_get_command_name_custom(self):
        from shalias.config import get_command_name
        self.assertEqual(get_command_name({"meta": {"command_name": "sa"}}), "sa")

    def test_corrupted_json_returns_blank(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            cfg_file = Path(td) / "config.json"
            cfg_file.write_text("not { json }")
            with patch("shalias.config.CONFIG_FILE", cfg_file):
                from shalias.config import load_config
                cfg = load_config()
        self.assertEqual(cfg["aliases"], {})


if __name__ == "__main__":
    unittest.main()
