import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestCommandSurface(unittest.TestCase):

    def test_help_epilog_lists_every_command(self):
        from shalias.cli import COMMANDS, HELP_EPILOG
        listed = set(re.findall(r"^  ([a-z-]+)\s{2,}\S", HELP_EPILOG, re.MULTILINE))
        self.assertEqual(listed, set(COMMANDS),
                         "HELP_EPILOG has drifted from the COMMANDS dict")

    def test_every_command_is_reachable_from_the_parser(self):
        from shalias.cli import COMMANDS, build_parser
        sub = [a for a in build_parser()._actions if hasattr(a, "choices") and a.choices]
        self.assertEqual(set(sub[0].choices), set(COMMANDS))

    def test_completions_use_the_real_command_list(self):
        from shalias.cli import COMMANDS
        from shalias.commands.shell_ops import _cmds
        self.assertEqual(set(_cmds().split()), set(COMMANDS))


if __name__ == "__main__":
    unittest.main()
