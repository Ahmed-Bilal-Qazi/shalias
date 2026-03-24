#!/usr/bin/env python3
"""
pathman.py — Windows Script PATH Manager
=========================================
Step 1:  python pathman.py install
Step 2:  open a NEW cmd window
Step 3:  pathman add myscript.py --alias mycommand
Step 4:  mycommand [args...]
"""

import os
import sys
import json
import shutil
import subprocess
import argparse
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────
HOME        = Path.home()
PATHMAN_DIR = HOME / ".pathman"
BIN_DIR     = PATHMAN_DIR / "bin"
CONFIG_FILE = PATHMAN_DIR / "config.json"

BANNER = r"""
  ____  ___  _____ _   _ __  __    _    _   _
 |  _ \/ _ \|_   _| | | |  \/  |  / \  | \ | |
 | |_) | | | | | | |_| | |\/| | / _ \ |  \| |
 |  __/| |_| | | |  _  | |  | |/ ___ \| |\  |
 |_|    \___/ |_| |_| |_|_|  |_/_/   \_\_| \_|
  Windows Script PATH Manager  v1.2
"""

# ── Config ────────────────────────────────────────────────────────────────────
def load_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if "aliases" not in data:
                data["aliases"] = {}
            return data
        except (json.JSONDecodeError, IOError):
            print("  WARNING: config.json is corrupted, starting fresh.")
    return {"aliases": {}}

def save_config(cfg: dict):
    PATHMAN_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)

# ── Registry / PATH helpers ───────────────────────────────────────────────────
def get_user_path_entries() -> list:
    """Read user PATH from registry. Returns [] if key or value is missing."""
    result = subprocess.run(
        ["reg", "query", "HKCU\\Environment", "/v", "PATH"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        # Key doesn't exist yet — fine, we'll create it
        return []
    for line in result.stdout.splitlines():
        line = line.strip()
        if "PATH" in line and "REG_" in line:
            parts = line.split(None, 2)
            if len(parts) == 3:
                return [p for p in parts[2].split(";") if p.strip()]
    return []

def set_user_path(entries: list):
    """
    Write user PATH to registry as REG_EXPAND_SZ.
    Deduplicates entries (case-insensitive) before writing.
    Uses setx to broadcast safely — never risks wiping PATH.
    """
    seen  = set()
    clean = []
    for e in entries:
        e = e.strip()
        if e and e.lower() not in seen:
            seen.add(e.lower())
            clean.append(e)

    path_str = ";".join(clean)

    result = subprocess.run(
        ["reg", "add", "HKCU\\Environment", "/v", "PATH",
         "/t", "REG_EXPAND_SZ", "/d", path_str, "/f"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"  ERROR: Failed to write PATH to registry.")
        print(f"         {result.stderr.strip()}")
        sys.exit(1)

    # Broadcast the change via setx so new CMD windows pick it up immediately.
    # We write a dummy variable then delete it — triggers WM_SETTINGCHANGE
    # without touching PATH at all. Safe.
    subprocess.run(["setx", "_PATHMAN_REFRESH", "1"], capture_output=True)
    subprocess.run(
        ["reg", "delete", "HKCU\\Environment", "/v", "_PATHMAN_REFRESH", "/f"],
        capture_output=True
    )

def add_to_path(new_entry: str):
    """Add a directory to user PATH if not already present."""
    entries = get_user_path_entries()
    if new_entry.lower() not in [e.lower() for e in entries]:
        entries.append(new_entry)
        set_user_path(entries)
        print(f"  OK  Added to PATH: {new_entry}")
    else:
        print(f"  OK  Already in PATH: {new_entry}")

def remove_from_path(entry: str):
    """Remove a directory from user PATH."""
    entries = get_user_path_entries()
    new_entries = [e for e in entries if e.lower() != entry.lower()]
    if len(new_entries) < len(entries):
        set_user_path(new_entries)
        print(f"  OK  Removed from PATH: {entry}")

# ── .bat launcher helpers ─────────────────────────────────────────────────────
def write_bat(alias: str, target: Path, interpreter: str) -> Path:
    """
    Create a .bat launcher in BIN_DIR.
    - Quotes interpreter to handle paths with spaces.
    - Quotes target script to handle paths with spaces.
    - %* forwards every argument the user types to the script unchanged.
    """
    BIN_DIR.mkdir(parents=True, exist_ok=True)
    bat_path = BIN_DIR / f"{alias}.bat"
    content = (
        "@echo off\n"
        f"\"{interpreter}\" \"{target}\" %*\n"
    )
    bat_path.write_text(content, encoding="utf-8")
    return bat_path

def remove_bat(alias: str):
    bat_path = BIN_DIR / f"{alias}.bat"
    if bat_path.exists():
        bat_path.unlink()

def detect_interpreter(script_path: Path) -> str:
    """Auto-detect interpreter from file extension."""
    return {
        ".py":  "python",
        ".js":  "node",
        ".rb":  "ruby",
        ".pl":  "perl",
        ".sh":  "bash",
        ".ps1": "powershell",
    }.get(script_path.suffix.lower(), "python")

def validate_alias(alias: str) -> bool:
    """Alias must be non-empty and contain only letters, digits, hyphens, underscores."""
    return bool(alias) and all(c.isalnum() or c in "-_" for c in alias)

# ── Commands ──────────────────────────────────────────────────────────────────
def cmd_install(args):
    print(BANNER)
    print("Installing pathman...")

    PATHMAN_DIR.mkdir(parents=True, exist_ok=True)
    BIN_DIR.mkdir(parents=True, exist_ok=True)

    # Resolve the real path to this script
    self_path = Path(sys.argv[0]).resolve()
    if not self_path.exists() or self_path.suffix.lower() != ".py":
        print(f"  ERROR: Can't find pathman.py at: {self_path}")
        print(f"         Make sure you run:  python pathman.py install")
        sys.exit(1)

    # Create pathman's own launcher bat
    bat = write_bat("pathman", self_path, "python")
    print(f"  OK  Launcher created : {bat}")
    print(f"  OK  Points to        : {self_path}")

    # Add bin dir to user PATH
    add_to_path(str(BIN_DIR))

    # Create config if it doesn't exist
    if not CONFIG_FILE.exists():
        save_config({"aliases": {}})
    print(f"  OK  Config file      : {CONFIG_FILE}")
    print()
    print("  Done! Open a NEW cmd window and run:  pathman list")
    print()

def cmd_add(args):
    script = Path(args.script).resolve()
    if not script.exists():
        print(f"  ERROR: Script not found: {script}")
        sys.exit(1)

    alias       = args.alias if args.alias else script.stem
    interpreter = args.interpreter if args.interpreter else detect_interpreter(script)

    if not validate_alias(alias):
        print(f"  ERROR: Invalid alias '{alias}'.")
        print("         Use only letters, numbers, hyphens (-) and underscores (_).")
        sys.exit(1)

    cfg = load_config()
    if alias in cfg["aliases"]:
        print(f"  ERROR: Alias '{alias}' already exists.")
        print(f"         To update it run:  pathman edit {alias}")
        sys.exit(1)

    cfg["aliases"][alias] = {
        "script":      str(script),
        "interpreter": interpreter,
    }
    save_config(cfg)
    bat = write_bat(alias, script, interpreter)

    print()
    print(f"  OK  Alias      : {alias}")
    print(f"      Script     : {script}")
    print(f"      Interpreter: {interpreter}")
    print(f"      Launcher   : {bat}")
    print(f"\n  You can now run from any CMD window:  {alias} [args...]")
    print()

def cmd_remove(args):
    cfg   = load_config()
    alias = args.alias
    if alias not in cfg["aliases"]:
        print(f"  ERROR: Alias '{alias}' not found.")
        print("         Run 'pathman list' to see all registered aliases.")
        sys.exit(1)
    remove_bat(alias)
    del cfg["aliases"][alias]
    save_config(cfg)
    print(f"  OK  Removed alias '{alias}'")

def cmd_list(args):
    cfg     = load_config()
    aliases = cfg.get("aliases", {})
    if not aliases:
        print()
        print("  No aliases registered yet.")
        print("  Add one:  pathman add myscript.py --alias mycommand")
        print()
        return
    print()
    print(f"  {'ALIAS':<20} {'INTERPRETER':<18} {'STATUS':<10} SCRIPT")
    print("  " + "-" * 80)
    for alias, info in sorted(aliases.items()):
        interp = info.get("interpreter", "python")
        script = info.get("script", "")
        status = "ok" if Path(script).exists() else "MISSING"
        print(f"  {alias:<20} {interp:<18} {status:<10} {script}")
    print()

def cmd_edit(args):
    cfg   = load_config()
    alias = args.alias
    if alias not in cfg["aliases"]:
        print(f"  ERROR: Alias '{alias}' not found.")
        print("         Run 'pathman list' to see all registered aliases.")
        sys.exit(1)

    info = dict(cfg["aliases"][alias])  # copy so we don't mutate the original

    if args.script:
        new_script = Path(args.script).resolve()
        if not new_script.exists():
            print(f"  ERROR: Script not found: {new_script}")
            sys.exit(1)
        info["script"] = str(new_script)

    if args.interpreter:
        info["interpreter"] = args.interpreter

    new_alias = args.new_alias if args.new_alias else alias

    if new_alias != alias:
        if not validate_alias(new_alias):
            print(f"  ERROR: Invalid alias '{new_alias}'.")
            print("         Use only letters, numbers, hyphens (-) and underscores (_).")
            sys.exit(1)
        if new_alias in cfg["aliases"]:
            print(f"  ERROR: Alias '{new_alias}' already exists.")
            sys.exit(1)
        # Delete old bat and config entry before creating the new one
        remove_bat(alias)
        del cfg["aliases"][alias]

    cfg["aliases"][new_alias] = info
    save_config(cfg)
    write_bat(new_alias, Path(info["script"]), info["interpreter"])

    label = f"'{alias}'" + (f" -> '{new_alias}'" if new_alias != alias else "")
    print(f"  OK  Updated {label}")
    cmd_list(args)

def cmd_config(args):
    if not CONFIG_FILE.exists():
        save_config({"aliases": {}})
    print(f"  Opening: {CONFIG_FILE}")
    os.startfile(str(CONFIG_FILE))

def cmd_uninstall(args):
    print()
    ans = input(
        "  This will:\n"
        f"    - Remove {BIN_DIR} from your user PATH\n"
        f"    - Delete all .bat launchers in {BIN_DIR}\n"
        f"    - Keep your config at {CONFIG_FILE}\n\n"
        "  Continue? [y/N] "
    ).strip().lower()
    if ans != "y":
        print("  Cancelled.")
        return
    remove_from_path(str(BIN_DIR))
    if BIN_DIR.exists():
        shutil.rmtree(BIN_DIR)
    print(f"  OK  Removed from PATH and deleted all launchers.")
    print(f"  OK  Config kept at: {CONFIG_FILE}")
    print()

# ── CLI wiring ────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        prog="pathman",
        description="Windows Script PATH Manager — run any script from CMD by name",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python pathman.py install
  pathman add deck.py --alias deck
  pathman add tools\\conv.js --alias conv --interpreter node
  pathman add C:\\scripts\\build.ps1 --alias build
  pathman add app.py --alias app --interpreter "C:\\envs\\myenv\\Scripts\\python"
  pathman list
  pathman edit deck --new-alias deckv2
  pathman edit deck --script C:\\new\\deck.py
  pathman edit deck --interpreter python3.11
  pathman remove deck
  pathman config
  pathman uninstall
        """
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("install",
        help="One-time setup: create launchers and add bin dir to PATH")

    p_add = sub.add_parser("add",
        help="Register a script as a CMD command")
    p_add.add_argument("script",
        help="Path to the script (.py .js .rb .ps1 etc.)")
    p_add.add_argument("--alias",
        help="Command name to type in CMD (default: filename without extension)")
    p_add.add_argument("--interpreter",
        help="Program to run the script (default: auto-detected from extension)")

    p_rem = sub.add_parser("remove",
        help="Unregister an alias and delete its launcher")
    p_rem.add_argument("alias",
        help="Alias name to remove")

    sub.add_parser("list",
        help="Show all registered aliases")

    p_edit = sub.add_parser("edit",
        help="Modify an existing alias")
    p_edit.add_argument("alias",
        help="Alias to modify")
    p_edit.add_argument("--new-alias", dest="new_alias",
        help="Rename the alias to this new name")
    p_edit.add_argument("--script",
        help="Point the alias to a different script file")
    p_edit.add_argument("--interpreter",
        help="Change the interpreter used to run the script")

    sub.add_parser("config",
        help="Open config.json in your default editor")

    sub.add_parser("uninstall",
        help="Remove pathman from PATH and delete all launchers")

    args = parser.parse_args()
    {
        "install":   cmd_install,
        "add":       cmd_add,
        "remove":    cmd_remove,
        "list":      cmd_list,
        "edit":      cmd_edit,
        "config":    cmd_config,
        "uninstall": cmd_uninstall,
    }[args.command](args)

if __name__ == "__main__":
    main()
