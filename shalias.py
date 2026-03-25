#!/usr/bin/env python3
"""
shalias.py — Cross-Platform Script Alias Manager
=================================================
Version 1.5

  Step 1:  python shalias.py install
  Step 2:  Open a NEW terminal window
  Step 3:  shalias add myscript.py --alias mycommand
  Step 4:  mycommand [args...]

Alias types
-----------
  run   — execute a script with an interpreter  (default)
  open  — open a file with the default application
  url   — open a URL in the default browser

GitHub: https://github.com/yourusername/shalias
"""

import os
import sys
import json
import shutil
import subprocess
import argparse
import tempfile
import platform
import re
from pathlib import Path

# ── Platform ──────────────────────────────────────────────────────────────────
IS_WINDOWS = platform.system() == "Windows"
IS_MACOS   = platform.system() == "Darwin"
IS_LINUX   = platform.system() == "Linux"
PLATFORM   = platform.system()

# ── Paths ─────────────────────────────────────────────────────────────────────
HOME        = Path.home()
SHALIAS_DIR = HOME / ".shalias"
BIN_DIR     = SHALIAS_DIR / "bin"
CONFIG_FILE = SHALIAS_DIR / "config.json"

VERSION = "1.5"

BANNER = r"""
   _____ _    _          _      _____
  / ____| |  | |   /\   | |    |_   _|   /\
 | (___ | |__| |  /  \  | |      | |    /  \
  \___ \|  __  | / /\ \ | |      | |   / /\ \
  ____) | |  | |/ ____ \| |____ _| |_ / ____ \
 |_____/|_|  |_/_/    \_\______|_____/_/    \_\
  Cross-Platform Script Alias Manager  v1.5
"""

ALIAS_TYPES = ("run", "open", "url")

# Extended interpreter map (v1.5)
INTERPRETER_MAP = {
    ".py":   "python3" if not IS_WINDOWS else "python",
    ".js":   "node",
    ".ts":   "ts-node",
    ".rb":   "ruby",
    ".pl":   "perl",
    ".sh":   "bash",
    ".ps1":  "powershell",
    ".lua":  "lua",
    ".php":  "php",
    ".r":    "Rscript",
    ".R":    "Rscript",
    ".go":   "go run",
}

# ── Config ────────────────────────────────────────────────────────────────────
def load_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            data.setdefault("aliases", {})
            data.setdefault("groups", {})
            return data
        except (json.JSONDecodeError, IOError):
            print("  WARNING: config.json is corrupted. Starting fresh.")
    return {"aliases": {}, "groups": {}}


def save_config(cfg: dict):
    """Atomic save: write to a temp file then replace to prevent corruption."""
    SHALIAS_DIR.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=str(SHALIAS_DIR), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
        shutil.move(tmp_path, CONFIG_FILE)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


# ── PATH management — Windows ─────────────────────────────────────────────────
def _win_get_user_path() -> list:
    """Read user PATH from the Windows registry."""
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


def _win_set_user_path(entries: list):
    """Write user PATH to the registry, deduplicating case-insensitively."""
    seen, clean = set(), []
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

    # Broadcast WM_SETTINGCHANGE so new CMD windows pick up the change.
    subprocess.run(["setx", "_SHALIAS_REFRESH", "1"], capture_output=True)
    subprocess.run(
        ["reg", "delete", "HKCU\\Environment", "/v", "_SHALIAS_REFRESH", "/f"],
        capture_output=True
    )


def _win_add_to_path(new_entry: str):
    entries = _win_get_user_path()
    if new_entry.lower() not in [e.lower() for e in entries]:
        entries.append(new_entry)
        _win_set_user_path(entries)
        print(f"  OK  Added to PATH : {new_entry}")
    else:
        print(f"  OK  Already in PATH: {new_entry}")


def _win_remove_from_path(entry: str):
    entries = _win_get_user_path()
    new_entries = [e for e in entries if e.lower() != entry.lower()]
    if len(new_entries) < len(entries):
        _win_set_user_path(new_entries)
        print(f"  OK  Removed from PATH: {entry}")


# ── PATH management — Unix (Linux / macOS) ────────────────────────────────────
def _unix_shell_configs() -> list:
    """Return all shell RC files that exist in the user's home directory."""
    candidates = [".bashrc", ".zshrc", ".profile", ".bash_profile"]
    return [HOME / f for f in candidates if (HOME / f).exists()]


def _unix_path_comment() -> str:
    return f'export PATH="{BIN_DIR}:$PATH"  # added by shalias'


def _unix_add_to_path():
    line    = _unix_path_comment()
    marker  = str(BIN_DIR)
    configs = _unix_shell_configs() or [HOME / ".bashrc"]
    added   = []

    for rc in configs:
        try:
            content = rc.read_text(encoding="utf-8") if rc.exists() else ""
            if marker not in content:
                with open(rc, "a", encoding="utf-8") as f:
                    f.write(f"\n{line}\n")
                added.append(str(rc))
        except IOError as e:
            print(f"  WARNING: Could not write to {rc}: {e}")

    if added:
        for f in added:
            print(f"  OK  Added PATH entry to : {f}")
    else:
        print(f"  OK  Already in PATH    : {BIN_DIR}")


def _unix_remove_from_path():
    marker = str(BIN_DIR)
    for rc in _unix_shell_configs():
        try:
            content = rc.read_text(encoding="utf-8")
            if marker in content:
                new_content = "\n".join(
                    ln for ln in content.splitlines() if marker not in ln
                ).strip() + "\n"
                rc.write_text(new_content, encoding="utf-8")
                print(f"  OK  Removed PATH entry from: {rc}")
        except IOError as e:
            print(f"  WARNING: Could not update {rc}: {e}")


# ── Unified PATH API ──────────────────────────────────────────────────────────
def add_to_path(win_entry: str = ""):
    if IS_WINDOWS:
        _win_add_to_path(win_entry or str(BIN_DIR))
    else:
        _unix_add_to_path()


def remove_from_path():
    if IS_WINDOWS:
        _win_remove_from_path(str(BIN_DIR))
    else:
        _unix_remove_from_path()


# ── Launcher helpers ──────────────────────────────────────────────────────────
def write_launcher(alias: str, alias_type: str, target: str, interpreter: str = "") -> Path:
    """
    Windows → .bat file in BIN_DIR
    Unix    → executable shell script (no extension) in BIN_DIR
    """
    BIN_DIR.mkdir(parents=True, exist_ok=True)

    if IS_WINDOWS:
        launcher_path = BIN_DIR / f"{alias}.bat"
        if alias_type == "run":
            content = f'@echo off\n"{interpreter}" "{target}" %*\n'
        elif alias_type in ("open", "url"):
            content = f'@echo off\nstart "" "{target}"\n'
        else:
            raise ValueError(f"Unknown alias type: '{alias_type}'")
        launcher_path.write_text(content, encoding="utf-8")

    else:  # Unix
        launcher_path = BIN_DIR / alias
        if alias_type == "run":
            content = f'#!/usr/bin/env bash\n"{interpreter}" "{target}" "$@"\n'
        elif alias_type == "open":
            opener  = "xdg-open" if IS_LINUX else "open"
            content = f'#!/usr/bin/env bash\n{opener} "{target}"\n'
        elif alias_type == "url":
            opener  = "xdg-open" if IS_LINUX else "open"
            content = f'#!/usr/bin/env bash\n{opener} "{target}"\n'
        else:
            raise ValueError(f"Unknown alias type: '{alias_type}'")
        launcher_path.write_text(content, encoding="utf-8")
        launcher_path.chmod(0o755)

    return launcher_path


def remove_launcher(alias: str):
    """Remove launcher regardless of whether it's a .bat or a bare script."""
    for name in [alias, f"{alias}.bat"]:
        p = BIN_DIR / name
        if p.exists():
            p.unlink()


def detect_interpreter(script_path: Path) -> str:
    """Return the default interpreter for a given file extension."""
    return INTERPRETER_MAP.get(
        script_path.suffix.lower(),
        "python3" if not IS_WINDOWS else "python"
    )


# ── Validators ────────────────────────────────────────────────────────────────
_SAFE_NAME_RE = re.compile(r'^[A-Za-z0-9_-]+$')


def validate_alias(alias: str) -> bool:
    """Alias must be non-empty: letters, digits, hyphens, underscores only."""
    return bool(alias) and bool(_SAFE_NAME_RE.match(alias))


def validate_group(group: str) -> bool:
    """Same rules as alias."""
    return bool(group) and bool(_SAFE_NAME_RE.match(group))


def validate_url(target: str) -> bool:
    return target.startswith("http://") or target.startswith("https://")


def _check_alias_valid_and_free(alias: str, cfg: dict):
    if not validate_alias(alias):
        print(f"  ERROR: Invalid alias '{alias}'.")
        print("         Use only letters, numbers, hyphens (-) and underscores (_).")
        sys.exit(1)
    if alias in cfg["aliases"]:
        print(f"  ERROR: Alias '{alias}' already exists.")
        print(f"         To update it, run:  shalias edit {alias}")
        sys.exit(1)


# ── Broken alias checker ──────────────────────────────────────────────────────
def warn_broken_aliases(cfg: dict):
    """
    Warn about aliases whose target file no longer exists on disk.
    URL aliases are skipped — they cannot be verified offline.
    """
    broken = [
        (alias, info.get("script", ""))
        for alias, info in cfg.get("aliases", {}).items()
        if info.get("type", "run") != "url"
        and info.get("script", "")
        and not Path(info["script"]).exists()
    ]
    if broken:
        print()
        print("  ⚠  WARNING: The following aliases point to missing files:")
        for alias, target in broken:
            print(f"       {alias:<20} → {target}")
        print("     Run 'shalias doctor' to review all issues,")
        print("     or 'shalias edit <alias> --script <new-path>' to fix.")
        print()


# ── Helper: print a formatted alias summary ───────────────────────────────────
def _print_alias_summary(alias: str, entry: dict, launcher: Path):
    atype = entry.get("type", "run")
    print()
    print(f"  OK  Alias      : {alias}")
    print(f"      Type       : {atype}")
    if atype == "url":
        print(f"      URL        : {entry['target']}")
    else:
        print(f"      Target     : {entry.get('script', '')}")
    if atype == "run":
        print(f"      Interpreter: {entry.get('interpreter', '')}")
    if entry.get("group"):
        print(f"      Group      : {entry['group']}")
    if entry.get("description"):
        print(f"      Description: {entry['description']}")
    print(f"      Launcher   : {launcher}")
    suffix = " [args...]" if atype == "run" else ""
    print(f"\n  You can now run from any terminal:  {alias}{suffix}")
    print()


# ══════════════════════════════════════════════════════════════════════════════
#  Commands
# ══════════════════════════════════════════════════════════════════════════════

def cmd_install(args):
    print(BANNER)
    print(f"  Platform  : {PLATFORM} ({platform.release()})")
    print(f"  Home      : {HOME}")
    print(f"  Install to: {SHALIAS_DIR}")
    print()

    SHALIAS_DIR.mkdir(parents=True, exist_ok=True)
    BIN_DIR.mkdir(parents=True, exist_ok=True)

    self_path = Path(sys.argv[0]).resolve()
    if not self_path.exists() or self_path.suffix.lower() != ".py":
        print(f"  ERROR: Can't locate shalias.py at: {self_path}")
        print("         Make sure you run:  python shalias.py install")
        sys.exit(1)

    interp    = "python" if IS_WINDOWS else "python3"
    launcher  = write_launcher("shalias", "run", str(self_path), interp)
    print(f"  OK  Launcher created : {launcher}")
    print(f"  OK  Points to        : {self_path}")

    add_to_path(str(BIN_DIR))

    if not CONFIG_FILE.exists():
        save_config({"aliases": {}, "groups": {}})
    print(f"  OK  Config           : {CONFIG_FILE}")
    print()

    if IS_WINDOWS:
        print("  Done! Open a NEW cmd window and run:  shalias list")
    else:
        print("  Done! Reload your shell config, then open a new terminal:")
        for rc in _unix_shell_configs():
            print(f"    source {rc}")
        print()
        print("  Then run:  shalias list")
    print()


# ── add ───────────────────────────────────────────────────────────────────────
def cmd_add(args):
    cfg        = load_config()
    warn_broken_aliases(cfg)
    alias_type = (args.type or "run").lower()

    if alias_type not in ALIAS_TYPES:
        print(f"  ERROR: Unknown type '{alias_type}'. Choose: {', '.join(ALIAS_TYPES)}")
        sys.exit(1)

    group = (args.group or "").strip()
    if group and not validate_group(group):
        print(f"  ERROR: Invalid group name '{group}'.")
        print("         Use only letters, numbers, hyphens and underscores.")
        sys.exit(1)

    # ── URL ───────────────────────────────────────────────────────────────────
    if alias_type == "url":
        target = args.script
        if not validate_url(target):
            print(f"  ERROR: Target doesn't look like a URL: {target}")
            print("         URLs must start with http:// or https://")
            sys.exit(1)

        alias = args.alias or ""
        if not alias:
            print("  ERROR: --alias is required for URL aliases.")
            sys.exit(1)

        _check_alias_valid_and_free(alias, cfg)

        entry = {
            "type":        "url",
            "target":      target,
            "description": args.description or "",
        }
        if group:
            entry["group"] = group

        cfg["aliases"][alias] = entry
        save_config(cfg)
        launcher = write_launcher(alias, "url", target)
        _print_alias_summary(alias, entry, launcher)
        return

    # ── open / run — target is a file path ───────────────────────────────────
    raw_target = args.script
    script     = Path(raw_target).resolve()

    if not script.exists():
        print(f"  ERROR: File not found: {script}")
        if " " in raw_target:
            print(f'\n  TIP : Quote paths that contain spaces:')
            print(f'        shalias add "{raw_target}" --type {alias_type} ...')
        sys.exit(1)

    alias = args.alias or script.stem
    _check_alias_valid_and_free(alias, cfg)

    if alias_type == "open":
        entry = {
            "type":        "open",
            "script":      str(script),
            "description": args.description or "",
        }
        if group:
            entry["group"] = group
        cfg["aliases"][alias] = entry
        save_config(cfg)
        launcher = write_launcher(alias, "open", str(script))

    else:  # run
        interpreter = args.interpreter or detect_interpreter(script)
        entry = {
            "type":        "run",
            "script":      str(script),
            "interpreter": interpreter,
            "description": args.description or "",
        }
        if group:
            entry["group"] = group
        cfg["aliases"][alias] = entry
        save_config(cfg)
        launcher = write_launcher(alias, "run", str(script), interpreter)

    _print_alias_summary(alias, entry, launcher)


# ── remove ────────────────────────────────────────────────────────────────────
def cmd_remove(args):
    cfg   = load_config()
    warn_broken_aliases(cfg)
    alias = args.alias

    if alias not in cfg["aliases"]:
        print(f"  ERROR: Alias '{alias}' not found.")
        print("         Run 'shalias list' to see all registered aliases.")
        sys.exit(1)

    remove_launcher(alias)
    del cfg["aliases"][alias]
    save_config(cfg)
    print(f"  OK  Removed alias '{alias}'")


# ── list ──────────────────────────────────────────────────────────────────────
def cmd_list(args):
    cfg     = load_config()
    warn_broken_aliases(cfg)
    aliases = cfg.get("aliases", {})

    group_filter = getattr(args, "group", None)
    if group_filter:
        aliases = {k: v for k, v in aliases.items()
                   if v.get("group", "") == group_filter}

    if not aliases:
        print()
        if group_filter:
            print(f"  No aliases in group '{group_filter}'.")
        else:
            print("  No aliases registered yet.")
            print("  Add a script :  shalias add myscript.py --alias mycommand")
            print("  Open a file  :  shalias add report.docx --alias report --type open")
            print("  Open a URL   :  shalias add https://example.com --alias ex --type url")
        print()
        return

    # Separate grouped from ungrouped
    grouped:   dict = {}
    ungrouped: dict = {}
    for alias, info in sorted(aliases.items()):
        g = info.get("group", "")
        if g:
            grouped.setdefault(g, {})[alias] = info
        else:
            ungrouped[alias] = info

    header = f"  {'ALIAS':<18} {'TYPE':<6} {'STATUS':<9} {'GROUP':<14} {'DESCRIPTION':<22} TARGET"
    divider = "  " + "─" * 100

    def _row(alias, info):
        atype  = info.get("type", "run")
        desc   = info.get("description", "")
        grp    = info.get("group", "")
        target = info.get("target", "") if atype == "url" else info.get("script", "")
        status = "ok" if (atype == "url" or Path(target).exists()) else "MISSING"
        print(f"  {alias:<18} {atype:<6} {status:<9} {grp:<14} {desc:<22} {target}")

    print()
    print(header)
    print(divider)

    for alias, info in ungrouped.items():
        _row(alias, info)

    for grp_name, members in sorted(grouped.items()):
        if ungrouped:
            print()
        print(f"  [{grp_name}]")
        for alias, info in sorted(members.items()):
            _row(alias, info)

    total = len(aliases)
    print()
    print(f"  {total} alias(es) registered.  "
          f"Use 'shalias search <term>' or 'shalias doctor' for more.")
    print()


# ── search ────────────────────────────────────────────────────────────────────
def cmd_search(args):
    """Full-text search across alias names, descriptions, targets, and groups."""
    cfg   = load_config()
    query = args.query.lower().strip()

    if not query:
        print("  ERROR: Search query cannot be empty.")
        sys.exit(1)

    found = {}
    for alias, info in cfg.get("aliases", {}).items():
        haystack = " ".join([
            alias,
            info.get("description", ""),
            info.get("target", ""),
            info.get("script", ""),
            info.get("group", ""),
            info.get("interpreter", ""),
        ]).lower()
        if query in haystack:
            found[alias] = info

    if not found:
        print(f"\n  No aliases found matching '{args.query}'.\n")
        return

    print(f"\n  {len(found)} result(s) for '{args.query}':\n")
    print(f"  {'ALIAS':<18} {'TYPE':<6} {'GROUP':<14} {'DESCRIPTION':<22} TARGET")
    print("  " + "─" * 90)
    for alias, info in sorted(found.items()):
        atype  = info.get("type", "run")
        desc   = info.get("description", "")
        grp    = info.get("group", "")
        target = info.get("target", "") if atype == "url" else info.get("script", "")
        print(f"  {alias:<18} {atype:<6} {grp:<14} {desc:<22} {target}")
    print()


# ── doctor ────────────────────────────────────────────────────────────────────
def cmd_doctor(args):
    """
    Audit every alias for:
      - Missing launcher file
      - Missing target file
      - Missing interpreter (run aliases)
    """
    cfg     = load_config()
    aliases = cfg.get("aliases", {})

    if not aliases:
        print("\n  No aliases to check.\n")
        return

    ok_count = missing_count = warning_count = 0

    print()
    print("  Running shalias doctor...\n")
    print(f"  {'ALIAS':<20} {'STATUS':<12} DETAIL")
    print("  " + "─" * 85)

    for alias, info in sorted(aliases.items()):
        atype  = info.get("type", "run")
        target = info.get("target", "") if atype == "url" else info.get("script", "")

        launcher = (BIN_DIR / f"{alias}.bat") if IS_WINDOWS else (BIN_DIR / alias)

        if not launcher.exists():
            print(f"  {alias:<20} {'NO LAUNCHER':<12} Re-add to regenerate: shalias remove {alias} && shalias add ...")
            warning_count += 1
            continue

        if atype == "url":
            print(f"  {alias:<20} {'OK':<12} {target}")
            ok_count += 1
            continue

        if not target:
            print(f"  {alias:<20} {'NO TARGET':<12} No script path stored in config")
            warning_count += 1
            continue

        if not Path(target).exists():
            print(f"  {alias:<20} {'MISSING':<12} {target}")
            missing_count += 1
            continue

        if atype == "run":
            interp = info.get("interpreter", "")
            # Handle interpreters with arguments (e.g. "go run")
            interp_bin = interp.split()[0] if interp else ""
            if interp_bin and not shutil.which(interp_bin):
                print(f"  {alias:<20} {'NO INTERP':<12} '{interp_bin}' not found in PATH")
                warning_count += 1
                continue

        print(f"  {alias:<20} {'OK':<12} {target}")
        ok_count += 1

    total = len(aliases)
    print()
    print(f"  ── Summary ────────────────────────────────────────")
    print(f"  Checked  : {total} alias(es)")
    print(f"  OK       : {ok_count}")
    print(f"  Missing  : {missing_count}")
    print(f"  Warnings : {warning_count}")

    if missing_count or warning_count:
        print()
        print("  Fix missing target :  shalias edit <alias> --script <new-path>")
        print("  Fix interpreter    :  shalias edit <alias> --interpreter <name>")
    print()


# ── edit ──────────────────────────────────────────────────────────────────────
def cmd_edit(args):
    cfg   = load_config()
    warn_broken_aliases(cfg)
    alias = args.alias

    if alias not in cfg["aliases"]:
        print(f"  ERROR: Alias '{alias}' not found.")
        print("         Run 'shalias list' to see all registered aliases.")
        sys.exit(1)

    info  = dict(cfg["aliases"][alias])
    atype = info.get("type", "run")

    # Update target / script
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
                    print(f'\n  TIP : Quote paths with spaces:')
                    print(f'        shalias edit {alias} --script "{args.script}"')
                sys.exit(1)
            info["script"] = str(new_script)

    # Update interpreter (run aliases only)
    if args.interpreter:
        if atype in ("open", "url"):
            print(f"  WARNING: --interpreter is ignored for type '{atype}' — skipping.")
        else:
            info["interpreter"] = args.interpreter

    # Update description
    if args.description is not None:
        info["description"] = args.description

    # Update group
    if args.group is not None:
        g = args.group.strip()
        if g and not validate_group(g):
            print(f"  ERROR: Invalid group name '{g}'.")
            print("         Use only letters, numbers, hyphens and underscores.")
            sys.exit(1)
        info["group"] = g  # empty string clears the group

    # Rename
    new_alias = args.new_alias or alias
    if new_alias != alias:
        if not validate_alias(new_alias):
            print(f"  ERROR: Invalid alias '{new_alias}'.")
            print("         Use only letters, numbers, hyphens (-) and underscores (_).")
            sys.exit(1)
        if new_alias in cfg["aliases"]:
            print(f"  ERROR: Alias '{new_alias}' already exists.")
            sys.exit(1)
        remove_launcher(alias)
        del cfg["aliases"][alias]

    cfg["aliases"][new_alias] = info
    save_config(cfg)

    target = info.get("target", "") if atype == "url" else info.get("script", "")
    write_launcher(new_alias, atype, target, info.get("interpreter", ""))

    label = f"'{alias}'" + (f" → '{new_alias}'" if new_alias != alias else "")
    print(f"  OK  Updated {label}")
    cmd_list(args)


# ── export ────────────────────────────────────────────────────────────────────
def cmd_export(args):
    cfg      = load_config()
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


# ── import ────────────────────────────────────────────────────────────────────
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

    cfg     = load_config()
    added   = 0
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
        write_launcher(alias, atype, target, interp)
        added += 1

    save_config(cfg)
    print(f"  OK  Imported {added} alias(es), skipped {skipped}.")
    if skipped:
        print("      Re-run with --overwrite to replace existing aliases.")


# ── config ────────────────────────────────────────────────────────────────────
def cmd_config(args):
    if not CONFIG_FILE.exists():
        save_config({"aliases": {}, "groups": {}})
    print(f"  Opening: {CONFIG_FILE}")
    if IS_WINDOWS:
        os.startfile(str(CONFIG_FILE))
    elif IS_MACOS:
        subprocess.run(["open", str(CONFIG_FILE)])
    else:
        editor = os.environ.get("EDITOR", "nano")
        subprocess.run([editor, str(CONFIG_FILE)])


# ── uninstall ─────────────────────────────────────────────────────────────────
def cmd_uninstall(args):
    print()
    ans = input(
        "  This will:\n"
        f"    - Remove {BIN_DIR} from your PATH\n"
        f"    - Delete all launchers in {BIN_DIR}\n"
        f"    - Keep your config at {CONFIG_FILE}\n\n"
        "  Continue? [y/N] "
    ).strip().lower()
    if ans != "y":
        print("  Cancelled.")
        return
    remove_from_path()
    if BIN_DIR.exists():
        shutil.rmtree(BIN_DIR)
    print("  OK  Removed from PATH and deleted all launchers.")
    print(f"  OK  Config preserved at: {CONFIG_FILE}")
    print()


# ── CLI wiring ────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        prog="shalias",
        description=f"shalias v{VERSION} — Cross-Platform Script Alias Manager",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=r"""
Examples:
  python shalias.py install

  # Run aliases (scripts executed by an interpreter)
  shalias add app.py --alias app
  shalias add tools/conv.js --alias conv --interpreter node
  shalias add build.ps1 --alias build --group devops
  shalias add report_gen.py --alias report --description "Monthly report" --group finance

  # Open aliases (files opened by their default application)
  shalias add notes.docx --alias notes --type open --group work
  shalias add budget.xlsx --alias budget --type open --group finance

  # URL aliases (opened in the default browser)
  shalias add https://github.com --alias gh --type url
  shalias add https://docs.python.org --alias pydocs --type url --group docs

  # Managing aliases
  shalias list
  shalias list --group devops
  shalias search github
  shalias doctor
  shalias edit app --new-alias myapp
  shalias edit app --script /new/path/app.py
  shalias edit app --group backend
  shalias edit app --group ""        # remove from group
  shalias remove app

  # Portability
  shalias export backup.json
  shalias import backup.json
  shalias import backup.json --overwrite

  shalias config
  shalias uninstall
        """
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # install
    sub.add_parser("install",
        help="One-time setup: create launcher and add bin dir to PATH")

    # add
    p_add = sub.add_parser("add",
        help="Register a script, file, or URL as a terminal command")
    p_add.add_argument("script",
        help="Path to a script/file, or a URL (http:// / https://). Quote paths with spaces.")
    p_add.add_argument("--alias",
        help="Command name (default: filename stem; required for URLs)")
    p_add.add_argument("--type", choices=ALIAS_TYPES, default="run",
        help="run = execute script (default)  |  open = open file  |  url = open URL")
    p_add.add_argument("--interpreter",
        help="Interpreter for the script (type=run only; auto-detected from extension by default)")
    p_add.add_argument("--description",
        help="Optional note shown in 'shalias list'")
    p_add.add_argument("--group",
        help="Assign alias to a named group (e.g. 'devops', 'docs', 'finance')")

    # remove
    p_rem = sub.add_parser("remove",
        help="Unregister an alias and delete its launcher")
    p_rem.add_argument("alias", help="Alias name to remove")

    # list
    p_list = sub.add_parser("list", help="Show all registered aliases")
    p_list.add_argument("--group",
        help="Filter output to a specific group")

    # search
    p_search = sub.add_parser("search",
        help="Search aliases by name, description, target, group, or interpreter")
    p_search.add_argument("query", help="Search term")

    # doctor
    sub.add_parser("doctor",
        help="Audit all aliases for issues (missing files, broken interpreters, orphaned launchers)")

    # edit
    p_edit = sub.add_parser("edit",
        help="Modify an existing alias")
    p_edit.add_argument("alias",           help="Alias to modify")
    p_edit.add_argument("--new-alias",     dest="new_alias",    help="Rename the alias")
    p_edit.add_argument("--script",        help="Point to a different file or URL")
    p_edit.add_argument("--interpreter",   help="Change the interpreter (type=run only)")
    p_edit.add_argument("--description",   help="Update the description (pass '' to clear)")
    p_edit.add_argument("--group",         help="Change the group (pass '' to remove from group)")

    # export
    p_exp = sub.add_parser("export",
        help="Export all aliases to a JSON file (backup / share across machines)")
    p_exp.add_argument("file", help="Output path (e.g. backup.json)")

    # import
    p_imp = sub.add_parser("import",
        help="Import aliases from a previously exported JSON file")
    p_imp.add_argument("file", help="Input path")
    p_imp.add_argument("--overwrite", action="store_true",
        help="Replace existing aliases that share the same name")

    # config
    sub.add_parser("config",
        help="Open config.json in your default editor")

    # uninstall
    sub.add_parser("uninstall",
        help="Remove shalias from PATH and delete all launchers")

    args = parser.parse_args()
    {
        "install":   cmd_install,
        "add":       cmd_add,
        "remove":    cmd_remove,
        "list":      cmd_list,
        "search":    cmd_search,
        "doctor":    cmd_doctor,
        "edit":      cmd_edit,
        "export":    cmd_export,
        "import":    cmd_import,
        "config":    cmd_config,
        "uninstall": cmd_uninstall,
    }[args.command](args)


if __name__ == "__main__":
    main()
