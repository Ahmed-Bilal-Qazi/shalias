import io
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestValidators(unittest.TestCase):

    def test_valid_aliases(self):
        from shalias.utils import validate_alias
        for name in ("myapp", "my-app", "my_app", "app123"):
            with self.subTest(name=name):
                self.assertTrue(validate_alias(name))

    def test_invalid_aliases(self):
        from shalias.utils import validate_alias
        for name in ("", "my app", "my.app", "my/app"):
            with self.subTest(name=name):
                self.assertFalse(validate_alias(name))

    def test_validate_url(self):
        from shalias.utils import validate_url
        self.assertTrue(validate_url("https://github.com"))
        self.assertTrue(validate_url("http://localhost:8080"))
        self.assertFalse(validate_url("github.com"))
        self.assertFalse(validate_url("ftp://example.com"))

    def test_parse_env_valid(self):
        from shalias.utils import parse_env
        self.assertEqual(parse_env(["PORT=8080", "DEBUG=true"]),
                         {"PORT": "8080", "DEBUG": "true"})

    def test_parse_env_empty(self):
        from shalias.utils import parse_env
        self.assertEqual(parse_env([]), {})
        self.assertEqual(parse_env(None), {})

    def test_parse_env_malformed_skipped(self):
        from shalias.utils import parse_env
        result = parse_env(["BADVALUE"])
        self.assertEqual(result, {})


class TestDetection(unittest.TestCase):

    def test_detect_type_url(self):
        from shalias.utils import detect_type
        self.assertEqual(detect_type("https://github.com"), "url")
        self.assertEqual(detect_type("http://localhost"),   "url")

    def test_detect_type_run(self):
        from shalias.utils import detect_type
        self.assertEqual(detect_type("script.py"), "run")
        self.assertEqual(detect_type("app.js"),    "run")

    def test_detect_type_open(self):
        from shalias.utils import detect_type
        self.assertEqual(detect_type("report.pdf"),  "open")
        self.assertEqual(detect_type("photo.png"),   "open")

    def test_detect_interpreter(self):
        from shalias.utils import detect_interpreter
        self.assertIn("python",  detect_interpreter(Path("script.py")))
        self.assertEqual("node", detect_interpreter(Path("app.js")))
        self.assertEqual("bash", detect_interpreter(Path("run.sh")))


class TestFormat(unittest.TestCase):

    def test_resolve_format_default(self):
        import types
        from shalias.utils import resolve_format
        ns = types.SimpleNamespace(format=None, json=False)
        self.assertEqual(resolve_format(ns), "table")

    def test_resolve_format_flag(self):
        import types
        from shalias.utils import resolve_format
        ns = types.SimpleNamespace(format="json", json=False)
        self.assertEqual(resolve_format(ns), "json")

    def test_resolve_format_legacy_json(self):
        import types
        from shalias.utils import resolve_format
        ns = types.SimpleNamespace(format=None, json=True)
        self.assertEqual(resolve_format(ns), "json")

    def test_format_aliases_json(self):
        from shalias.utils import format_aliases
        aliases = {"myapp": {"type": "run", "script": "/tmp/app.py", "use_count": 3}}
        captured = io.StringIO()
        with patch("sys.stdout", captured):
            format_aliases(aliases, "json")
        data = json.loads(captured.getvalue())
        self.assertIn("myapp", data)

    def test_format_aliases_plain(self):
        from shalias.utils import format_aliases
        aliases = {"gl": {"type": "inline", "target": "git log", "use_count": 0}}
        captured = io.StringIO()
        with patch("sys.stdout", captured):
            format_aliases(aliases, "plain")
        out = captured.getvalue()
        self.assertIn("gl",     out)
        self.assertIn("inline", out)

    def test_format_stats_json(self):
        from shalias.utils import format_stats
        aliases = {
            "myapp":  {"use_count": 5, "last_used": "2025-01-01T00:00:00+00:00"},
            "unused": {"use_count": 0},
        }
        captured = io.StringIO()
        with patch("sys.stdout", captured):
            format_stats(aliases, "json")
        data = json.loads(captured.getvalue())
        self.assertEqual(data["total_runs"], 5)
        self.assertEqual(len(data["aliases"]), 1)

    def test_format_stats_plain(self):
        from shalias.utils import format_stats
        aliases = {"gl": {"use_count": 2, "last_used": "2025-06-01T00:00:00+00:00"}}
        captured = io.StringIO()
        with patch("sys.stdout", captured):
            format_stats(aliases, "plain")
        out = captured.getvalue()
        self.assertIn("gl", out)
        self.assertIn("2",  out)


if __name__ == "__main__":
    unittest.main()
