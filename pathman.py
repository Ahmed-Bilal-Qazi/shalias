#!/usr/bin/env python3
"""
pathman.py — Windows Script PATH Manager
=========================================
Step 1:  python pathman.py install
Step 2:  open a NEW cmd window
Step 3:  pathman add myscript.py --alias mycommand
Step 4:  mycommand [args...]

Alias types
-----------
  run   — execute a script with an interpreter (default)
  open  — open any file with its default Windows app
  url   — open a URL in the default browser
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
  Windows Script PATH Manager  v1.3
"""

ALIAS_TYPES = ("run", "open", "url")

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
    """Read user PATH from the registry. Returns [] if the key/value is missing."""
    result = subprocess.run(
        ["reg", "query", "HKCU\\Environment", "/v", "PATH"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
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
    Broadcasts the change via a dummy setx so new CMD windows pick it up.
    """
    seen  = set()
    clean = []
    for e in entries:
        e = e.strip()
        if e and e.lower() not in seen:
            seen.add(e.lower())
            clean.append(e)

    result = subprocess.run(
        ["reg", "add", "HKCU\\Environment", "/v", "PATH",
         "/t", "REG_EXPAND_SZ", "/d", ";".join(clean), "/f"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print("  ERROR: Failed to write PATH to registry.")
        print(f"         {result.stderr.strip()}")
        sys.exit(1)

    # Broadcast WM_SETTINGCHANGE so new CMD windows pick up the change immediately.
    # Write a dummy var then delete it — never touches PATH.
    subprocess.run(["setx", "_PATHMAN_REFRESH", "1"], capture_output=True)
    subprocess.run(
        ["reg", "delete", "HKCU\\Environment", "/v", "_PATHMAN_REFRESH", "/f"],
        capture_output=True
    )


def add_to_path(new_entry: str):
    """Add a directory to the user PATH if not already present."""
    entries = get_user_path_entries()
    if new_entry.lower() not in [e.lower() for e in entries]:
        entries.append(new_entry)
        set_user_path(entries)
        print(f"  OK  Added to PATH: {new_entry}")
    else:
        print(f"  OK  Already in PATH: {new_entry}")


def remove_from_path(entry: str):
    """Remove a directory from the user PATH."""
    entries = get_user_path_entries()
    new_entries = [e for e in entries if e.lower() != entry.lower()]
    if len(new_entries) < len(entries):
        set_user_path(new_entries)
        print(f"  OK  Removed from PATH: {entry}")


# ── .bat launcher helpers ─────────────────────────────────────────────────────
def write_bat(alias: str, alias_type: str, target: str, interpreter: str = "") -> Path:
    """
    Write a .bat launcher to BIN_DIR.

      run   → "interpreter" "script" %*   (forwards all arguments)
      open  → start "" "file"             (opens with default Windows app)
      url   → start "" "https://..."      (opens in default browser)
    """
    BIN_DIR.mkdir(parents=True, exist_ok=True)
    bat_path = BIN_DIR / f"{alias}.bat"

    if alias_type == "run":
        content = f'@echo off\n"{interpreter}" "{target}" %*\n'
    elif alias_type in ("open", "url"):
        content = f'@echo off\nstart "" "{target}"\n'
    else:
        raise ValueError(f"Unknown alias type: '{alias_type}'. Expected one of: {ALIAS_TYPES}")

    bat_path.write_text(content, encoding="utf-8")
    return bat_path


def remove_bat(alias: str):
    bat_path = BIN_DIR / f"{alias}.bat"
    if bat_path.exists():
        bat_path.unlink()


def detect_interpreter(script_path: Path) -> str:
    """Return the default interpreter for a given file extension."""
    return {
        ".py":  "python",
        ".js":  "node",
        ".rb":  "ruby",
        ".pl":  "perl",
        ".sh":  "bash",
        ".ps1": "powershell",
    }.get(script_path.suffix.lower(), "python")


# ── Validators ────────────────────────────────────────────────────────────────
def validate_alias(alias: str) -> bool:
    """Alias must be non-empty and contain only letters, digits, hyphens, underscores."""
    return bool(alias) and all(c.isalnum() or c in "-_" for c in alias)


def validate_url(target: str) -> bool:
    """Minimal check: target must start with http:// or https://."""
    return target.startswith("http://") or target.startswith("https://")


# ── Broken alias checker ──────────────────────────────────────────────────────
def warn_broken_aliases(cfg: dict):
    """
    Warn about any alias whose target file no longer exists on disk.
    Runs automatically at the start of every command.
    URL aliases are skipped — they cannot be verified offline.
    """
    broken = []
    for alias, info in cfg.get("aliases", {}).items():
        atype = info.get("type", "run")
        if atype == "url":
            continue
        target = info.get("script", "")
        if target and not Path(target).exists():
            broken.append((alias, target))

    if broken:
        print()
        print("  ⚠  WARNING: The following aliases point to missing files:")
        for alias, target in broken:
            print(f"       {alias:<20} → {target}")
        print("     Run 'pathman list' for details, "
              "or 'pathman edit <alias> --script <new-path>' to fix.")
        print()


# ── Commands ──────────────────────────────────────────────────────────────────
def cmd_install(args):
    print(BANNER)
    print("Installing pathman...")

    PATHMAN_DIR.mkdir(parents=True, exist_ok=True)
    BIN_DIR.mkdir(parents=True, exist_ok=True)

    self_path = Path(sys.argv[0]).resolve()
    if not self_path.exists() or self_path.suffix.lower() != ".py":
        print(f"  ERROR: Can't find pathman.py at: {self_path}")
        print("         Make sure you run:  python pathman.py install")
        sys.exit(1)

    bat = write_bat("pathman", "run", str(self_path), "python")
    print(f"  OK  Launcher created : {bat}")
    print(f"  OK  Points to        : {self_path}")

    add_to_path(str(BIN_DIR))

    if not CONFIG_FILE.exists():
        save_config({"aliases": {}})
    print(f"  OK  Config file      : {CONFIG_FILE}")
    print()
    print("  Done! Open a NEW cmd window and run:  pathman list")
    print()


def cmd_add(args):
    cfg = load_config()
    warn_broken_aliases(cfg)

    alias_type = (args.type or "run").lower()
    if alias_type not in ALIAS_TYPES:
        print(f"  ERROR: Unknown type '{alias_type}'. Choose from: {', '.join(ALIAS_TYPES)}")
        sys.exit(1)

    # ── URL alias ─────────────────────────────────────────────────────────────
    if alias_type == "url":
        target = args.script   # positional arg doubles as the URL for url-type
        if not validate_url(target):
            print(f"  ERROR: Target doesn't look like a URL: {target}")
            print("         URLs must start with http:// or https://")
            sys.exit(1)

        alias = args.alias or ""
        if not alias:
            print("  ERROR: --alias is required for URL aliases.")
            sys.exit(1)
        if not validate_alias(alias):
            print(f"  ERROR: Invalid alias '{alias}'.")
            print("         Use only letters, numbers, hyphens (-) and underscores (_).")
            sys.exit(1)
        if alias in cfg["aliases"]:
            print(f"  ERROR: Alias '{alias}' already exists.")
            print(f"         To update it, run:  pathman edit {alias}")
            sys.exit(1)

        description = args.description or ""
        cfg["aliases"][alias] = {
            "type":        "url",
            "target":      target,
            "description": description,
        }
        save_config(cfg)
        bat = write_bat(alias, "url", target)

        print()
        print(f"  OK  Alias      : {alias}")
        print(f"      Type       : url")
        print(f"      URL        : {target}")
        if description:
            print(f"      Description: {description}")
        print(f"      Launcher   : {bat}")
        print(f"\n  You can now run from any CMD window:  {alias}")
        print()
        return

    # ── open / run alias — target is a file path ──────────────────────────────
    raw_target = args.script
    script = Path(raw_target).resolve()

    if not script.exists():
        print(f"  ERROR: File not found: {script}")
        if " " in raw_target:
            print()
            print("  TIP : Your path contains spaces. Always quote paths with spaces:")
            print(f'        pathman add "{raw_target}" --type {alias_type} ...')
        sys.exit(1)

    alias       = args.alias or script.stem
    description = args.description or ""

    if not validate_alias(alias):
        print(f"  ERROR: Invalid alias '{alias}'.")
        print("         Use only letters, numbers, hyphens (-) and underscores (_).")
        sys.exit(1)
    if alias in cfg["aliases"]:
        print(f"  ERROR: Alias '{alias}' already exists.")
        print(f"         To update it, run:  pathman edit {alias}")
        sys.exit(1)

    if alias_type == "open":
        cfg["aliases"][alias] = {
            "type":        "open",
            "script":      str(script),
            "description": description,
        }
        save_config(cfg)
        bat = write_bat(alias, "open", str(script))

        print()
        print(f"  OK  Alias      : {alias}")
        print(f"      Type       : open (opens with default app)")
        print(f"      Target     : {script}")
        if description:
            print(f"      Description: {description}")
        print(f"      Launcher   : {bat}")
        print(f"\n  You can now run from any CMD window:  {alias}")
        print()

    else:  # run
        interpreter = args.interpreter or detect_interpreter(script)
        cfg["aliases"][alias] = {
            "type":        "run",
            "script":      str(script),
            "interpreter": interpreter,
            "description": description,
        }
        save_config(cfg)
        bat = write_bat(alias, "run", str(script), interpreter)

        print()
        print(f"  OK  Alias      : {alias}")
        print(f"      Type       : run")
        print(f"      Script     : {script}")
        print(f"      Interpreter: {interpreter}")
        if description:
            print(f"      Description: {description}")
        print(f"      Launcher   : {bat}")
        print(f"\n  You can now run from any CMD window:  {alias} [args...]")
        print()


def cmd_remove(args):
    cfg   = load_config()
    warn_broken_aliases(cfg)
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
    warn_broken_aliases(cfg)
    aliases = cfg.get("aliases", {})

    if not aliases:
        print()
        print("  No aliases registered yet.")
        print("  Add a script :  pathman add myscript.py --alias mycommand")
        print("  Open a file  :  pathman add report.docx --alias report --type open")
        print("  Open a URL   :  pathman add https://example.com --alias ex --type url")
        print()
        return

    print()
    print(f"  {'ALIAS':<18} {'TYPE':<6} {'STATUS':<9} {'DESCRIPTION':<22} TARGET")
    print("  " + "-" * 90)
    for alias, info in sorted(aliases.items()):
        atype  = info.get("type", "run")
        desc   = info.get("description", "")
        target = info.get("target", "") if atype == "url" else info.get("script", "")
        status = "ok" if (atype == "url" or Path(target).exists()) else "MISSING"
        print(f"  {alias:<18} {atype:<6} {status:<9} {desc:<22} {target}")
    print()


def cmd_edit(args):
    cfg   = load_config()
    warn_broken_aliases(cfg)
    alias = args.alias

    if alias not in cfg["aliases"]:
        print(f"  ERROR: Alias '{alias}' not found.")
        print("         Run 'pathman list' to see all registered aliases.")
        sys.exit(1)

    info  = dict(cfg["aliases"][alias])   # work on a copy
    atype = info.get("type", "run")

    # ── Update target / script ────────────────────────────────────────────────
    if args.script:
        if atype == "url":
            if not validate_url(args.script):
                print(f"  ERROR: New target doesn't look like a URL: {args.script}")
                print("         URLs must start with http:// or https://")
                sys.exit(1)
            info["target"] = args.script
        else:
            new_script = Path(args.script).resolve()
            if not new_script.exists():
                print(f"  ERROR: File not found: {new_script}")
                if " " in args.script:
                    print()
                    print("  TIP : Your path contains spaces. Quote it:")
                    print(f'        pathman edit {alias} --script "{args.script}"')
                sys.exit(1)
            info["script"] = str(new_script)

    # ── Update interpreter (run aliases only) ─────────────────────────────────
    if args.interpreter:
        if atype in ("open", "url"):
            print(f"  WARNING: --interpreter is ignored for type '{atype}' and will be skipped.")
        else:
            info["interpreter"] = args.interpreter

    # ── Update description ────────────────────────────────────────────────────
    if args.description is not None:
        info["description"] = args.description

    # ── Rename if requested ───────────────────────────────────────────────────
    new_alias = args.new_alias or alias

    if new_alias != alias:
        if not validate_alias(new_alias):
            print(f"  ERROR: Invalid alias '{new_alias}'.")
            print("         Use only letters, numbers, hyphens (-) and underscores (_).")
            sys.exit(1)
        if new_alias in cfg["aliases"]:
            print(f"  ERROR: Alias '{new_alias}' already exists.")
            sys.exit(1)
        remove_bat(alias)
        del cfg["aliases"][alias]

    cfg["aliases"][new_alias] = info
    save_config(cfg)

    target = info.get("target", "") if atype == "url" else info.get("script", "")
    write_bat(new_alias, atype, target, info.get("interpreter", ""))

    label = f"'{alias}'" + (f" -> '{new_alias}'" if new_alias != alias else "")
    print(f"  OK  Updated {label}")
    cmd_list(args)


def cmd_export(args):
    cfg = load_config()
    warn_broken_aliases(cfg)
    out_path = Path(args.file).resolve()
    try:
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
        count = len(cfg.get("aliases", {}))
        print(f"  OK  Exported {count} alias(es) to: {out_path}")
    except IOError as e:
        print(f"  ERROR: Could not write to {out_path}: {e}")
        sys.exit(1)


def cmd_import(args):
    in_path = Path(args.file).resolve()
    if not in_path.exists():
        print(f"  ERROR: File not found: {in_path}")
        sys.exit(1)
    try:
        with open(in_path, "r", encoding="utf-8") as f:
            imported = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"  ERROR: Could not read {in_path}: {e}")
        sys.exit(1)

    incoming = imported.get("aliases", {})
    if not incoming:
        print("  Nothing to import (no aliases found in file).")
        return

    cfg    = load_config()
    added  = 0
    skipped = 0

    for alias, info in incoming.items():
        if alias in cfg["aliases"] and not args.overwrite:
            print(f"  SKIP  '{alias}' already exists (use --overwrite to replace)")
            skipped += 1
            continue

        atype  = info.get("type", "run")
        target = info.get("target", "") if atype == "url" else info.get("script", "")
        interp = info.get("interpreter", "")

        if atype != "url" and target and not Path(target).exists():
            print(f"  WARN  '{alias}' — target missing on this machine: {target}")

        cfg["aliases"][alias] = info
        write_bat(alias, atype, target, interp)
        added += 1

    save_config(cfg)
    print(f"  OK  Imported {added} alias(es), skipped {skipped}.")
    if skipped:
        print("      Re-run with --overwrite to replace existing aliases.")


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
    print("  OK  Removed from PATH and deleted all launchers.")
    print(f"  OK  Config kept at: {CONFIG_FILE}")
    print()


# ── CLI wiring ────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        prog="pathman",
        description="Windows Script PATH Manager — run any script from CMD by name",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=r"""
Examples:
  python pathman.py install

  # Run aliases (scripts executed by an interpreter)
  pathman add deck.py --alias deck
  pathman add tools\conv.js --alias conv --interpreter node
  pathman add "C:\my scripts\build.ps1" --alias build
  pathman add app.py --alias app --interpreter "C:\envs\myenv\Scripts\python"
  pathman add report_gen.py --alias report --description "Generate monthly report"

  # Open aliases (files opened by their default Windows app)
  pathman add "C:\docs\notes.docx" --alias notes --type open
  pathman add "C:\user\test drive\report.pdf" --alias report --type open
  pathman add C:\data\budget.xlsx --alias budget --type open --description "Q3 budget"

  # URL aliases (opened in the default browser)
  pathman add https://github.com --alias gh --type url
  pathman add https://docs.python.org --alias pydocs --type url --description "Python docs"

  # Managing aliases
  pathman list
  pathman edit deck --new-alias deckv2
  pathman edit deck --script "C:\new path\deck.py"
  pathman edit notes --description "Weekly notes"
  pathman remove deck

  # Portability
  pathman export aliases_backup.json
  pathman import aliases_backup.json
  pathman import aliases_backup.json --overwrite

  pathman config
  pathman uninstall
        """
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # install
    sub.add_parser("install",
        help="One-time setup: create launcher and add bin dir to PATH")

    # add
    p_add = sub.add_parser("add",
        help="Register a script, file, or URL as a CMD command")
    p_add.add_argument("script",
        help=(
            "Path to a script/file (.py .docx .pdf etc.) or a URL "
            "(http:// / https://). QUOTE paths that contain spaces."
        ))
    p_add.add_argument("--alias",
        help="Command name to use in CMD (default: filename stem for files; "
             "required for URLs)")
    p_add.add_argument("--type", choices=ALIAS_TYPES, default="run",
        help="run = execute script (default), "
             "open = open file with default app, "
             "url = open URL in browser")
    p_add.add_argument("--interpreter",
        help="Interpreter used to run the script (type=run only; "
             "default: auto-detected from extension)")
    p_add.add_argument("--description",
        help="Optional note shown in 'pathman list'")

    # remove
    p_rem = sub.add_parser("remove",
        help="Unregister an alias and delete its launcher")
    p_rem.add_argument("alias", help="Alias name to remove")

    # list
    sub.add_parser("list", help="Show all registered aliases")

    # edit
    p_edit = sub.add_parser("edit",
        help="Modify an existing alias")
    p_edit.add_argument("alias", help="Alias to modify")
    p_edit.add_argument("--new-alias", dest="new_alias",
        help="Rename the alias")
    p_edit.add_argument("--script",
        help="Point the alias to a different file or URL")
    p_edit.add_argument("--interpreter",
        help="Change the interpreter (type=run aliases only)")
    p_edit.add_argument("--description",
        help="Update the description (pass '' to clear)")

    # export
    p_exp = sub.add_parser("export",
        help="Export all aliases to a JSON file (backup / new machine)")
    p_exp.add_argument("file",
        help="Output path (e.g. aliases_backup.json)")

    # import
    p_imp = sub.add_parser("import",
        help="Import aliases from a previously exported JSON file")
    p_imp.add_argument("file",
        help="Input path")
    p_imp.add_argument("--overwrite", action="store_true",
        help="Replace existing aliases that share the same name")

    # config
    sub.add_parser("config",
        help="Open config.json in your default editor")

    # uninstall
    sub.add_parser("uninstall",
        help="Remove pathman from PATH and delete all launchers")

    args = parser.parse_args()
    {
        "install":   cmd_install,
        "add":       cmd_add,
        "remove":    cmd_remove,
        "list":      cmd_list,
        "edit":      cmd_edit,
        "export":    cmd_export,
        "import":    cmd_import,
        "config":    cmd_config,
        "uninstall": cmd_uninstall,
    }[args.command](args)


if __name__ == "__main__":
    main()
