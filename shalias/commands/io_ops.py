"""
shalias export, import, update, config, uninstall, rename-cmd
"""
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

from ..colors import _g, _r, _y
from ..config import backup_config, load_config, save_config, get_command_name
from ..constants import (
    BIN_DIR, CONFIG_FILE, IS_MACOS, IS_WINDOWS, UPDATE_URL, VERSION,
)
from ..launcher import write_launcher, remove_launcher
from ..path_manager import remove_from_path
from ..utils import now_stamp, validate_alias


def cmd_export(args):
    cfg  = load_config()
    path = Path(args.output)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
    print(_g(f"  + Exported to {path}"))


def cmd_import(args):
    path    = Path(args.input)
    dry_run = getattr(args, "dry_run", False)

    if not path.exists():
        print(_r(f"  File not found: {path}"))
        sys.exit(1)
    try:
        with open(path, "r", encoding="utf-8") as f:
            imported = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(_r(f"  Couldn't read {path}: {e}"))
        sys.exit(1)

    aliases = imported.get("aliases", {})
    if not aliases:
        print(_y("  No aliases found in the file."))
        return

    print(f"\n  {'DRY RUN — ' if dry_run else ''}Importing {len(aliases)} alias(es):\n")
    for alias, info in aliases.items():
        print(f"    {alias:<20} {info.get('type', 'run'):<8} "
              f"{info.get('script', info.get('target', ''))}")

    if dry_run:
        print("\n  (dry run — nothing was changed)\n")
        return

    cfg = load_config()
    backup_config()
    for alias, info in aliases.items():
        cfg["aliases"][alias] = info
        write_launcher(alias, info)
    save_config(cfg)
    print(_g(f"\n  + Imported {len(aliases)} aliases\n"))


def cmd_update(args):
    print("  Checking for updates...")
    try:
        req = urllib.request.Request(UPDATE_URL, method="GET")
        req.add_header("User-Agent", f"shalias/{VERSION}")
        with urllib.request.urlopen(req, timeout=8) as resp:
            remote_src = resp.read().decode("utf-8")
        m = re.search(r'^VERSION\s*=\s*["\']([^"\']+)["\']', remote_src, re.MULTILINE)
        if not m:
            print(_y("  Couldn't parse the remote version — try again later."))
            return
        remote_ver = m.group(1)
        if remote_ver == VERSION:
            print(_g(f"  You're already on the latest version ({VERSION})."))
            return
        print(_y(f"  New version: {remote_ver}  (you have {VERSION})"))
        self_path = Path(sys.argv[0]).resolve()
        self_path.write_text(remote_src, encoding="utf-8")
        print(_g(f"  + Updated to {remote_ver}"))
    except Exception as e:
        print(_r(f"  Update failed: {e}"))


def cmd_config(args):
    if IS_WINDOWS:
        subprocess.run(["notepad", str(CONFIG_FILE)])
    elif IS_MACOS:
        subprocess.run(["open", str(CONFIG_FILE)])
    else:
        editor = os.environ.get("EDITOR", "nano")
        subprocess.run([editor, str(CONFIG_FILE)])


def cmd_uninstall(args):
    print("\n  Removing shalias from PATH...")
    remove_from_path()
    if BIN_DIR.exists():
        shutil.rmtree(BIN_DIR)
        print(_g("  + Launchers removed"))
    print()
    print("  Your aliases are still saved at ~/.shalias/config.json")
    print("  Delete it manually if you want a completely clean slate.")
    print()
    print("  Bye! o/")
    print()


def cmd_rename_cmd(args):
    """
    Register a new command name so users can call shalias by a shorter name.
    Creates a thin launcher wrapper in ~/.shalias/bin/<name>.
    The original 'shalias' command is untouched as a fallback.
    """
    new_name = args.name.strip()

    if not validate_alias(new_name):
        print(_r(f"  '{new_name}' isn't a valid command name."))
        print("  Use only letters, numbers, hyphens (-), and underscores (_).")
        sys.exit(1)

    if new_name == "shalias":
        print(_y("  That's already the default name — nothing to do."))
        return

    # Build a launcher that just forwards to the real shalias binary
    import shalias.cli as _cli_mod
    cli_path = Path(_cli_mod.__file__).resolve()
    py       = sys.executable

    entry = {
        "type":        "run",
        "script":      str(cli_path),
        "interpreter": py,
        "description": f"shalias alias: {new_name}",
        "added":       now_stamp(),
        "env":         {},
        "cwd":         "",
    }
    launcher = write_launcher(new_name, entry)

    # Persist the preferred name so help text and hints use it
    cfg = load_config()
    old_name = get_command_name(cfg)
    cfg.setdefault("meta", {})["command_name"] = new_name

    # Remove old custom launcher if the name changed
    if old_name not in ("shalias", new_name):
        remove_launcher(old_name)

    save_config(cfg)

    print(_g(f"\n  + '{new_name}' is now an alias for shalias"))
    print(f"    Launcher : {launcher}")
    print(f"    You can now use '{new_name}' everywhere instead of 'shalias'.")
    print(f"    The original 'shalias' command still works as a fallback.\n")
