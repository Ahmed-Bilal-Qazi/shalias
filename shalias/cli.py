#!/usr/bin/env python3
"""
shalias - Cross-Platform Script Alias Manager
Entry point: parses args and dispatches to the right command module.

Changelog
---------
4.0  Modular rewrite (commands/, config, launcher, path_manager, utils)
     26 commands trimmed to 13 - search folded into list, run-group into
     run --group, rename/freeze/unfreeze into edit flags
     usage tracking dropped - it cost ~190ms per alias call on Windows
     new: which, edit --enable/--disable, install-aware update
3.0  Auto-detect type - alias chaining - env var injection - inline commands
     clone - --cwd - instant list - opt-in --check
2.0  Parallel execution - groups - usage stats - locking - JSON output
     dry-run import - shell autocompletion - doctor
1.0  Initial release
"""
import argparse
import sys

from .constants import VERSION
from .commands.install    import cmd_install
from .commands.alias_ops  import cmd_add, cmd_remove
from .commands.edit        import cmd_edit
from .commands.list_search import cmd_list
from .commands.run_ops     import cmd_run, cmd_doctor
from .commands.io_ops      import (
    cmd_export, cmd_import, cmd_update, cmd_uninstall,
)
from .commands.shell_ops   import cmd_completion
from .commands.which       import cmd_which


# ── Argument parser ───────────────────────────────────────────────────────────

# Thirteen commands in one flat list is a wall of text on first contact, so the
# six you actually use daily go up top and the rest are grouped underneath.
HELP_EPILOG = """
everyday
  add          Register a script, file, URL, or command
  list         Show your aliases (add a word to filter)
  run          Run one or more aliases
  which        Show what an alias points to
  edit         Change an alias, or lock/disable it
  remove       Delete an alias

setup
  install      One-time setup on this machine
  doctor       Find and fix broken aliases (--fix)
  update       Update shalias itself
  uninstall    Remove shalias and every launcher

moving between machines
  export       Save all aliases to a JSON file
  import       Load aliases from a JSON file
  completion   Print a shell completion script

Run 'shalias <command> --help' for the details on any one of them.
"""


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="shalias",
        description="shalias - run your scripts from anywhere",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=HELP_EPILOG,
    )
    p.add_argument("--version", action="version", version=f"shalias {VERSION}")
    sub = p.add_subparsers(dest="command", metavar="<command>")

    # install
    sub.add_parser("install")

    # add
    a = sub.add_parser("add")
    a.add_argument("script",        nargs="?",        help="Script/file path, URL, or shell command (with --inline)")
    a.add_argument("--chain",       nargs="+", metavar="ALIAS",
                   help="Make this alias run other aliases, in order")
    a.add_argument("--alias",       "-a",             help="Name for the command (default: filename stem)")
    a.add_argument("--type",        "-t",             help="Override auto-detected type: run | open | url")
    a.add_argument("--interpreter", "-i",             help="Override interpreter (e.g. python3, node)")
    a.add_argument("--inline",      action="store_true", help="Treat the first arg as a raw shell command")
    a.add_argument("--cwd",                           help="Working dir: 'script' | 'current' | /absolute/path")
    a.add_argument("--env",         action="append",  metavar="KEY=VAL",
                   help="Bake an env var into the launcher (repeatable)")
    a.add_argument("--group",       "-g",             help="Assign to a group")
    a.add_argument("--description", "-d",             help="Short description")

    # remove
    rm = sub.add_parser("remove")
    rm.add_argument("alias")

    # list
    ls = sub.add_parser("list")
    ls.add_argument("pattern",  nargs="?",
                    help="Only show aliases matching this text")
    ls.add_argument("--group",  "-g",   help="Filter by group")
    ls.add_argument("--type",   "-t",   help="Filter by type: run | open | url | inline | chain")
    ls.add_argument("--sort",   choices=["recent"],
                    help="Sort by most recently added")
    ls.add_argument("--check",  action="store_true",
                    help="Also verify that file targets still exist")
    ls.add_argument("--format", "-f",   choices=["table", "json", "plain"],
                    default="table",    help="Output format (default: table)")
    # Legacy flag kept for backwards compat
    ls.add_argument("--json",   action="store_true", help=argparse.SUPPRESS)

    # run
    ru = sub.add_parser("run")
    ru.add_argument("aliases", nargs="*",  help="Alias name(s)")
    ru.add_argument("--group",    "-g",    help="Run every alias in this group")
    ru.add_argument("--parallel", action="store_true", help="Run them all at the same time")

    # which
    wh = sub.add_parser("which")
    wh.add_argument("alias")

    # doctor
    doc = sub.add_parser("doctor")
    doc.add_argument("--fix", action="store_true",
                     help="Auto-remove aliases pointing to missing files")

    # edit
    ed = sub.add_parser("edit")
    ed.add_argument("alias")
    ed.add_argument("--new-alias",   dest="new_alias",    help="Rename the alias")
    ed.add_argument("--script",      "-s",                help="New script or file path")
    ed.add_argument("--type",        "-t",                help="New type: run | open | url | inline")
    ed.add_argument("--interpreter", "-i",                help="New interpreter")
    ed.add_argument("--cwd",                              help="New working directory")
    ed.add_argument("--env",         action="append", metavar="KEY=VAL",
                    help="Add or update env vars")
    ed.add_argument("--description", "-d",                help="New description")
    ed.add_argument("--group",       "-g",                help="New group")
    ed.add_argument("--lock",    action="store_true",
                    help="Protect this alias from edits and removal")
    ed.add_argument("--unlock",  action="store_true", help="Drop that protection")
    ed.add_argument("--disable", action="store_true",
                    help="Turn the alias off but keep its settings")
    ed.add_argument("--enable",  action="store_true", help="Turn it back on")

    # export / import
    ex = sub.add_parser("export")
    ex.add_argument("output", nargs="?", default="shalias_backup.json")
    im = sub.add_parser("import")
    im.add_argument("input")
    im.add_argument("--dry-run", action="store_true", dest="dry_run",
                    help="Preview what would be imported, without applying it")

    # update
    sub.add_parser("update")

    # completion
    co = sub.add_parser("completion")
    co.add_argument("shell", choices=["bash", "zsh", "fish", "powershell"])

    # uninstall
    sub.add_parser("uninstall")

    return p


# ── Command dispatch table ────────────────────────────────────────────────────

COMMANDS = {
    "install":    cmd_install,
    "add":        cmd_add,
    "remove":     cmd_remove,
    "list":       cmd_list,
    "run":        cmd_run,
    "which":      cmd_which,
    "doctor":     cmd_doctor,
    "edit":       cmd_edit,
    "export":     cmd_export,
    "import":     cmd_import,
    "update":     cmd_update,
    "completion": cmd_completion,
    "uninstall":  cmd_uninstall,
}


def main() -> None:
    parser = build_parser()
    args   = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    fn = COMMANDS.get(args.command)
    if not fn:
        from .colors import _r
        print(_r(f"  Unknown command: {args.command}"))
        parser.print_help()
        sys.exit(1)

    fn(args)


if __name__ == "__main__":
    main()
