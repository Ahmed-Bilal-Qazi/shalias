#!/usr/bin/env python3
"""
shalias.py — Cross-Platform Script Alias Manager
=================================================
Version 2.0

  Step 1:  python shalias.py install
  Step 2:  Open a NEW terminal window
  Step 3:  shalias add myscript.py --alias mycommand
  Step 4:  mycommand [args...]

Alias types
-----------
  run   — execute a script with an interpreter  (default)
  open  — open a file with the default application
  url   — open a URL in the default browser

GitHub: https://github.com/Ahmed-Bilal-Qazi/shalias
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
import threading
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

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
BACKUP_DIR  = SHALIAS_DIR / "backups"

VERSION = "2.0"

# Remote source for self-update checks — update this to your real repo URL
UPDATE_URL = "https://raw.githubusercontent.com/Ahmed-Bilal-Qazi/shalias/main/shalias.py"

BANNER = r"""
   _____ _    _          _      _____
  / ____| |  | |   /\   | |    |_   _|   /\
 | (___ | |__| |  /  \  | |      | |    /  \
  \___ \|  __  | / /\ \ | |      | |   / /\ \
  ____) | |  | |/ ____ \| |____ _| |_ / ____ \
 |_____/|_|  |_/_/    \_\______|_____/_/    \_\
  Cross-Platform Script Alias Manager  v2.0
"""

ALIAS_TYPES = ("run", "open", "url")

# Extended interpreter map
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


# ── Color helpers ─────────────────────────────────────────────────────────────
def _color_enabled() -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    return sys.stdout.isatty()

_USE_COLOR = None

def _c_code(name: str) -> str:
    global _USE_COLOR
    if _USE_COLOR is None:
        _USE_COLOR = _color_enabled()
    if not _USE_COLOR:
        return ""
    return {
        "green":  "\033[32m",
        "yellow": "\033[33m",
        "red":    "\033[31m",
        "cyan":   "\033[36m",
        "bold":   "\033[1m",
        "dim":    "\033[2m",
        "reset":  "\033[0m",
    }.get(name, "")

def _g(s):  return f"{_c_code('green')}{s}{_c_code('reset')}"
def _y(s):  return f"{_c_code('yellow')}{s}{_c_code('reset')}"
def _r(s):  return f"{_c_code('red')}{s}{_c_code('reset')}"
def _c(s):  return f"{_c_code('cyan')}{s}{_c_code('reset')}"
def _b(s):  return f"{_c_code('bold')}{s}{_c_code('reset')}"
def _d(s):  return f"{_c_code('dim')}{s}{_c_code('reset')}"


# ── Config ────────────────────────────────────────────────────────────────────
def load_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            data.setdefault("aliases", {})
            data.setdefault("groups", {})
            data.setdefault("meta", {})
            return data
        except (json.JSONDecodeError, IOError):
            print(_y("  WARNING: config.json is corrupted. Starting fresh."))
    return {"aliases": {}, "groups": {}, "meta": {}}


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


def backup_config():
    """Snapshot config.json before any destructive operation."""
    if not CONFIG_FILE.exists():
        return
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    ts  = datetime.now().strftime("%Y%m%d_%H%M%S")
    dst = BACKUP_DIR / f"config_{ts}.json"
    shutil.copy2(CONFIG_FILE, dst)
    # keep only the 10 most recent backups
    backups = sorted(BACKUP_DIR.glob("config_*.json"), reverse=True)
    for old in backups[10:]:
        try:
            old.unlink()
        except OSError:
            pass


# ── PATH management — Windows ─────────────────────────────────────────────────
def _win_get_user_path() -> list:
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
        print(_r("  ERROR: Failed to write PATH to registry."))
        print(f"         {result.stderr.strip()}")
        sys.exit(1)

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
        print(_g(f"  OK  Added to PATH : {new_entry}"))
    else:
        print(_g(f"  OK  Already in PATH: {new_entry}"))


def _win_remove_from_path(entry: str):
    entries = _win_get_user_path()
    new_entries = [e for e in entries if e.lower() != entry.lower()]
    if len(new_entries) < len(entries):
        _win_set_user_path(new_entries)
        print(_g(f"  OK  Removed from PATH: {entry}"))


# ── PATH management — Unix ────────────────────────────────────────────────────
def _unix_shell_configs() -> list:
    candidates = [
        ".bashrc", ".zshrc", ".profile", ".bash_profile",
        ".config/fish/config.fish",
    ]
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
            print(_y(f"  WARNING: Could not write to {rc}: {e}"))

    if added:
        for f in added:
            print(_g(f"  OK  Added PATH entry to : {f}"))
    else:
        print(_g(f"  OK  Already in PATH    : {BIN_DIR}"))


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
                print(_g(f"  OK  Removed PATH entry from: {rc}"))
        except IOError as e:
            print(_y(f"  WARNING: Could not update {rc}: {e}"))


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

    The launcher also records usage stats via a fire-and-forget callback to
    'shalias _track <alias>'. Errors from that call are silenced so they
    never interrupt the user's actual script.
    """
    BIN_DIR.mkdir(parents=True, exist_ok=True)
    self_path = Path(sys.argv[0]).resolve()
    py        = sys.executable

    if IS_WINDOWS:
        launcher_path = BIN_DIR / f"{alias}.bat"
        track_line    = f'"{py}" "{self_path}" _track {alias} 2>nul\n'
        if alias_type == "run":
            content = f'@echo off\n{track_line}"{interpreter}" "{target}" %*\n'
        elif alias_type in ("open", "url"):
            content = f'@echo off\n{track_line}start "" "{target}"\n'
        else:
            raise ValueError(f"Unknown alias type: '{alias_type}'")
        launcher_path.write_text(content, encoding="utf-8")

    else:  # Unix
        launcher_path = BIN_DIR / alias
        track_line    = f'"{py}" "{self_path}" _track {alias} 2>/dev/null &\n'
        if alias_type == "run":
            content = (
                f'#!/usr/bin/env bash\n'
                f'{track_line}'
                f'"{interpreter}" "{target}" "$@"\n'
            )
        elif alias_type == "open":
            opener  = "xdg-open" if IS_LINUX else "open"
            content = f'#!/usr/bin/env bash\n{track_line}{opener} "{target}"\n'
        elif alias_type == "url":
            opener  = "xdg-open" if IS_LINUX else "open"
            content = f'#!/usr/bin/env bash\n{track_line}{opener} "{target}"\n'
        else:
            raise ValueError(f"Unknown alias type: '{alias_type}'")
        launcher_path.write_text(content, encoding="utf-8")
        launcher_path.chmod(0o755)

    return launcher_path


def remove_launcher(alias: str):
    for name in [alias, f"{alias}.bat"]:
        p = BIN_DIR / name
        if p.exists():
            p.unlink()


def detect_interpreter(script_path: Path) -> str:
    return INTERPRETER_MAP.get(
        script_path.suffix.lower(),
        "python3" if not IS_WINDOWS else "python"
    )


# ── Validators ────────────────────────────────────────────────────────────────
_SAFE_NAME_RE = re.compile(r'^[A-Za-z0-9_-]+$')


def validate_alias(alias: str) -> bool:
    return bool(alias) and bool(_SAFE_NAME_RE.match(alias))


def validate_group(group: str) -> bool:
    return bool(group) and bool(_SAFE_NAME_RE.match(group))


def validate_url(target: str) -> bool:
    return target.startswith("http://") or target.startswith("https://")


def _check_alias_valid_and_free(alias: str, cfg: dict):
    if not validate_alias(alias):
        print(_r(f"  ERROR: Invalid alias '{alias}'."))
        print("         Use only letters, numbers, hyphens (-) and underscores (_).")
        sys.exit(1)
    if alias in cfg["aliases"]:
        print(_r(f"  ERROR: Alias '{alias}' already exists."))
        print(f"         To update it, run:  shalias edit {alias}")
        sys.exit(1)


# ── Broken alias checker ──────────────────────────────────────────────────────
def warn_broken_aliases(cfg: dict):
    broken = [
        (alias, info.get("script", ""))
        for alias, info in cfg.get("aliases", {}).items()
        if info.get("type", "run") != "url"
        and info.get("script", "")
        and not Path(info["script"]).exists()
    ]
    if broken:
        print()
        print(_y("  ⚠  WARNING: The following aliases point to missing files:"))
        for alias, target in broken:
            print(f"       {alias:<20} → {target}")
        print("     Run 'shalias doctor' to review all issues,")
        print("     or 'shalias edit <alias> --script <new-path>' to fix.")
        print()


# ── Helper: print a formatted alias summary ───────────────────────────────────
def _print_alias_summary(alias: str, entry: dict, launcher: Path):
    atype = entry.get("type", "run")
    print()
    print(_g(f"  OK  Alias      : {alias}"))
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
    if entry.get("locked"):
        print(_y("      Locked     : yes"))
    print(f"      Launcher   : {launcher}")
    suffix = " [args...]" if atype == "run" else ""
    print(f"\n  You can now run from any terminal:  {_b(alias)}{suffix}")
    print()


# ── Auto-update check (background, at most once per day) ─────────────────────
def _check_update_async(cfg: dict):
    """
    Silently poll for a newer version once per day.
    Prints a one-line hint if an update is available; never blocks the CLI.
    """
    meta = cfg.setdefault("meta", {})
    last = meta.get("last_update_check", 0)
    if time.time() - last < 86400:
        return

    def _do_check():
        try:
            req = urllib.request.Request(UPDATE_URL, method="GET")
            req.add_header("User-Agent", f"shalias/{VERSION}")
            with urllib.request.urlopen(req, timeout=4) as resp:
                remote_src = resp.read(4096).decode("utf-8", errors="ignore")
            m = re.search(r'^VERSION\s*=\s*["\']([^"\']+)["\']', remote_src, re.MULTILINE)
            if m:
                remote_ver = m.group(1)
                if remote_ver != VERSION:
                    print(_y(
                        f"\n  ↑  shalias {remote_ver} is available"
                        f" (you have {VERSION}). Run: shalias update\n"
                    ))
        except Exception:
            pass  # never crash the main command

    meta["last_update_check"] = time.time()
    save_config(cfg)
    t = threading.Thread(target=_do_check, daemon=True)
    t.start()
    t.join(timeout=4)


# ══════════════════════════════════════════════════════════════════════════════
#  Internal: usage tracking  (called from generated launchers)
# ══════════════════════════════════════════════════════════════════════════════
def cmd_track(args):
    """Update use_count and last_used for an alias. Called from launchers only."""
    try:
        cfg = load_config()
        alias = args.alias
        if alias in cfg["aliases"]:
            entry = cfg["aliases"][alias]
            entry["use_count"] = entry.get("use_count", 0) + 1
            entry["last_used"] = datetime.now(timezone.utc).isoformat()
            save_config(cfg)
    except Exception:
        pass  # tracking must never break the user's script


# ══════════════════════════════════════════════════════════════════════════════
#  Commands
# ══════════════════════════════════════════════════════════════════════════════

# ── install ───────────────────────────────────────────────────────────────────
def cmd_install(args):
    print(BANNER)
    print(f"  Platform  : {PLATFORM} ({platform.release()})")
    print(f"  Home      : {HOME}")
    print(f"  Install to: {SHALIAS_DIR}")
    print()

    SHALIAS_DIR.mkdir(parents=True, exist_ok=True)
    BIN_DIR.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    self_path = Path(sys.argv[0]).resolve()
    if not self_path.exists() or self_path.suffix.lower() != ".py":
        print(_r(f"  ERROR: Can't locate shalias.py at: {self_path}"))
        print("         Make sure you run:  python shalias.py install")
        sys.exit(1)

    interp   = "python" if IS_WINDOWS else "python3"
    launcher = write_launcher("shalias", "run", str(self_path), interp)
    print(_g(f"  OK  Launcher created : {launcher}"))
    print(_g(f"  OK  Points to        : {self_path}"))

    add_to_path(str(BIN_DIR))

    if not CONFIG_FILE.exists():
        save_config({"aliases": {}, "groups": {}, "meta": {}})
    print(_g(f"  OK  Config           : {CONFIG_FILE}"))
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
    _check_update_async(cfg)
    alias_type = (args.type or "run").lower()

    if alias_type not in ALIAS_TYPES:
        print(_r(f"  ERROR: Unknown type '{alias_type}'. Choose: {', '.join(ALIAS_TYPES)}"))
        sys.exit(1)

    group = (args.group or "").strip()
    if group and not validate_group(group):
        print(_r(f"  ERROR: Invalid group name '{group}'."))
        print("         Use only letters, numbers, hyphens and underscores.")
        sys.exit(1)

    # ── URL ───────────────────────────────────────────────────────────────────
    if alias_type == "url":
        target = args.script
        if not validate_url(target):
            print(_r(f"  ERROR: Target doesn't look like a URL: {target}"))
            print("         URLs must start with http:// or https://")
            sys.exit(1)

        alias = args.alias or ""
        if not alias:
            print(_r("  ERROR: --alias is required for URL aliases."))
            sys.exit(1)

        _check_alias_valid_and_free(alias, cfg)

        entry = {
            "type":        "url",
            "target":      target,
            "description": args.description or "",
            "use_count":   0,
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
        print(_r(f"  ERROR: File not found: {script}"))
        if " " in raw_target:
            print(f'\n  TIP : Quote paths that contain spaces:')
            print(f'        shalias add "{raw_target}" --type {alias_type} ...')
        sys.exit(1)

    alias = args.alias or script.stem
    _check_alias_valid_and_free(alias, cfg)

    base_entry = {
        "description": args.description or "",
        "use_count":   0,
    }
    if group:
        base_entry["group"] = group

    if alias_type == "open":
        entry = {**base_entry, "type": "open", "script": str(script)}
        cfg["aliases"][alias] = entry
        save_config(cfg)
        launcher = write_launcher(alias, "open", str(script))
    else:  # run
        interpreter = args.interpreter or detect_interpreter(script)
        entry = {
            **base_entry,
            "type":        "run",
            "script":      str(script),
            "interpreter": interpreter,
        }
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
        print(_r(f"  ERROR: Alias '{alias}' not found."))
        print("         Run 'shalias list' to see all registered aliases.")
        sys.exit(1)

    if cfg["aliases"][alias].get("locked"):
        print(_r(f"  ERROR: Alias '{alias}' is locked. Run: shalias unfreeze {alias}"))
        sys.exit(1)

    backup_config()
    remove_launcher(alias)
    del cfg["aliases"][alias]
    save_config(cfg)
    print(_g(f"  OK  Removed alias '{alias}'"))


# ── list ──────────────────────────────────────────────────────────────────────
def cmd_list(args):
    cfg     = load_config()
    warn_broken_aliases(cfg)
    _check_update_async(cfg)
    aliases = cfg.get("aliases", {})

    group_filter = getattr(args, "group", None)
    if group_filter:
        aliases = {k: v for k, v in aliases.items()
                   if v.get("group", "") == group_filter}

    json_out = getattr(args, "json", False)

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

    if json_out:
        print(json.dumps(aliases, indent=2))
        return

    grouped:   dict = {}
    ungrouped: dict = {}
    for alias, info in sorted(aliases.items()):
        g = info.get("group", "")
        if g:
            grouped.setdefault(g, {})[alias] = info
        else:
            ungrouped[alias] = info

    # Column widths adjusted for color escape codes
    header  = f"  {'ALIAS':<20} {'TYPE':<6} {'STATUS':<9} {'GROUP':<14} {'USES':<6} {'DESCRIPTION':<22} TARGET"
    divider = "  " + "─" * 105

    def _row(alias, info):
        atype  = info.get("type", "run")
        desc   = (info.get("description", "") or "")[:22]
        grp    = info.get("group", "")
        target = info.get("target", "") if atype == "url" else info.get("script", "")
        uses   = str(info.get("use_count", 0))
        ok     = atype == "url" or Path(target).exists()
        status = _g("ok") if ok else _r("MISSING")
        lock   = " 🔒" if info.get("locked") else ""
        name   = alias + lock
        # raw padding (status contains color codes, pad on raw string length)
        status_pad = status + (" " * max(0, 9 - len("ok" if ok else "MISSING")))
        print(f"  {name:<20} {atype:<6} {status_pad}  {grp:<14} {uses:<6} {desc:<22} {_d(target)}")

    print()
    print(_b(header))
    print(divider)

    for alias, info in ungrouped.items():
        _row(alias, info)

    for grp_name, members in sorted(grouped.items()):
        if ungrouped:
            print()
        print(_c(f"  [{grp_name}]"))
        for alias, info in sorted(members.items()):
            _row(alias, info)

    total = len(aliases)
    print()
    print(_d(f"  {total} alias(es) registered.  "
             "Use 'shalias search <term>' or 'shalias doctor' for more."))
    print()


# ── search ────────────────────────────────────────────────────────────────────
def cmd_search(args):
    cfg   = load_config()
    query = args.query.lower().strip()

    if not query:
        print(_r("  ERROR: Search query cannot be empty."))
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

    print(f"\n  {len(found)} result(s) for '{_b(args.query)}':\n")
    print(f"  {'ALIAS':<20} {'TYPE':<6} {'GROUP':<14} {'USES':<6} {'DESCRIPTION':<22} TARGET")
    print("  " + "─" * 95)
    for alias, info in sorted(found.items()):
        atype  = info.get("type", "run")
        desc   = (info.get("description", "") or "")[:22]
        grp    = info.get("group", "")
        uses   = str(info.get("use_count", 0))
        target = info.get("target", "") if atype == "url" else info.get("script", "")
        print(f"  {alias:<20} {atype:<6} {grp:<14} {uses:<6} {desc:<22} {_d(target)}")
    print()


# ── doctor ────────────────────────────────────────────────────────────────────
def cmd_doctor(args):
    cfg     = load_config()
    aliases = cfg.get("aliases", {})
    do_fix  = getattr(args, "fix", False)

    if not aliases:
        print("\n  No aliases to check.\n")
        return

    ok_count = missing_count = warning_count = fixed_count = 0
    to_remove = []

    print()
    print("  Running shalias doctor...\n")
    print(f"  {'ALIAS':<20} {'STATUS':<14} DETAIL")
    print("  " + "─" * 85)

    for alias, info in sorted(aliases.items()):
        atype    = info.get("type", "run")
        target   = info.get("target", "") if atype == "url" else info.get("script", "")
        launcher = (BIN_DIR / f"{alias}.bat") if IS_WINDOWS else (BIN_DIR / alias)

        if not launcher.exists():
            print(f"  {alias:<20} {_y('NO LAUNCHER'):<22} Re-add: shalias remove {alias} && shalias add ...")
            warning_count += 1
            continue

        if atype == "url":
            print(f"  {alias:<20} {_g('OK'):<22} {target}")
            ok_count += 1
            continue

        if not target:
            print(f"  {alias:<20} {_r('NO TARGET'):<22} No script path in config")
            warning_count += 1
            continue

        if not Path(target).exists():
            missing_count += 1
            if do_fix:
                to_remove.append(alias)
                print(f"  {alias:<20} {_r('REMOVED'):<22} {target}")
                fixed_count += 1
            else:
                print(f"  {alias:<20} {_r('MISSING'):<22} {target}")
            continue

        if atype == "run":
            interp     = info.get("interpreter", "")
            interp_bin = interp.split()[0] if interp else ""
            if interp_bin and not shutil.which(interp_bin):
                print(f"  {alias:<20} {_y('NO INTERP'):<22} '{interp_bin}' not found in PATH")
                warning_count += 1
                continue

        print(f"  {alias:<20} {_g('OK'):<22} {_d(target)}")
        ok_count += 1

    if do_fix and to_remove:
        backup_config()
        for alias in to_remove:
            remove_launcher(alias)
            del cfg["aliases"][alias]
        save_config(cfg)

    total = len(aliases)
    print()
    print("  ── Summary ─────────────────────────────────────────")
    print(f"  Checked  : {total}")
    print(f"  {_g('OK')}       : {ok_count}")
    print(f"  Missing  : {missing_count}")
    print(f"  Warnings : {warning_count}")
    if do_fix:
        print(f"  Fixed    : {fixed_count}")

    if (missing_count or warning_count) and not do_fix:
        print()
        print("  Fix missing target :  shalias edit <alias> --script <new-path>")
        print("  Fix interpreter    :  shalias edit <alias> --interpreter <name>")
        print("  Auto-remove broken :  shalias doctor --fix")
    print()


# ── edit ──────────────────────────────────────────────────────────────────────
def cmd_edit(args):
    """
    Modify an existing alias.
    With no field flags, drops into an interactive prompt so you can
    change any field without memorising flag names.
    """
    cfg   = load_config()
    warn_broken_aliases(cfg)
    alias = args.alias

    if alias not in cfg["aliases"]:
        print(_r(f"  ERROR: Alias '{alias}' not found."))
        print("         Run 'shalias list' to see all registered aliases.")
        sys.exit(1)

    if cfg["aliases"][alias].get("locked"):
        print(_r(f"  ERROR: Alias '{alias}' is locked. Run: shalias unfreeze {alias}"))
        sys.exit(1)

    info  = dict(cfg["aliases"][alias])
    atype = info.get("type", "run")

    # Detect interactive mode: no field flag was given
    field_flags = [
        args.new_alias, args.script, args.interpreter,
        args.description, args.group, args.type,
    ]
    interactive = not any(f is not None for f in field_flags)

    if interactive:
        print(f"\n  Editing alias: {_b(alias)}\n")
        print(_d("  Press Enter to keep the current value. Type a single space to clear a field.\n"))

        def _prompt(label, current):
            val = input(f"  {label:<18} [{current}]: ").strip()
            if val == " ":
                return ""
            return val if val else current

        new_alias_input = _prompt("Alias name", alias)
        new_type_input  = ""
        while True:
            nt = _prompt(f"Type (run/open/url)", atype)
            if nt in ALIAS_TYPES:
                new_type_input = nt
                break
            elif nt == atype:
                new_type_input = atype
                break
            print(_y(f"    Invalid type '{nt}'. Choose: run, open, url"))

        if new_type_input == "url":
            new_script_input = _prompt("URL", info.get("target", ""))
        else:
            new_script_input = _prompt("Script path", info.get("script", ""))

        new_interp_input = ""
        if new_type_input == "run":
            new_interp_input = _prompt("Interpreter", info.get("interpreter", ""))

        new_desc_raw  = input(f"  {'Description':<18} [{info.get('description', '')}]: ").strip()
        new_desc      = new_desc_raw if new_desc_raw != "" else info.get("description", "")
        if new_desc_raw == " ":
            new_desc = ""

        new_group_raw = input(f"  {'Group':<18} [{info.get('group', '') or 'none'}]: ").strip()
        new_group     = new_group_raw if new_group_raw != "" else info.get("group", "")
        if new_group_raw == " ":
            new_group = ""

        print()
        # wire into standard flag handling below
        args.new_alias    = new_alias_input   if new_alias_input   != alias               else None
        args.type         = new_type_input    if new_type_input    != atype               else None
        args.script       = new_script_input  if new_script_input  != info.get("script", info.get("target", "")) else None
        args.interpreter  = new_interp_input  if new_interp_input  != info.get("interpreter", "") else None
        args.description  = new_desc
        args.group        = new_group

    # ── Apply changes ─────────────────────────────────────────────────────────

    # Change type
    if args.type and args.type in ALIAS_TYPES:
        atype        = args.type
        info["type"] = atype

    # Update target / script
    if args.script:
        if atype == "url":
            if not validate_url(args.script):
                print(_r(f"  ERROR: Not a valid URL: {args.script}"))
                print("         URLs must start with http:// or https://")
                sys.exit(1)
            info["target"] = args.script
            info.pop("script", None)
        else:
            new_script = Path(args.script).resolve()
            if not new_script.exists():
                print(_r(f"  ERROR: File not found: {new_script}"))
                if " " in args.script:
                    print(f'\n  TIP : Quote paths with spaces:')
                    print(f'        shalias edit {alias} --script "{args.script}"')
                sys.exit(1)
            info["script"] = str(new_script)
            info.pop("target", None)

    # Update interpreter
    if args.interpreter is not None:
        if atype in ("open", "url"):
            print(_y(f"  WARNING: --interpreter ignored for type '{atype}'."))
        else:
            info["interpreter"] = args.interpreter

    # Update description (empty string clears it)
    if args.description is not None:
        info["description"] = args.description

    # Update group (empty string removes group)
    if args.group is not None:
        g = args.group.strip()
        if g and not validate_group(g):
            print(_r(f"  ERROR: Invalid group name '{g}'."))
            sys.exit(1)
        if g:
            info["group"] = g
        else:
            info.pop("group", None)

    # Rename
    new_alias = args.new_alias or alias
    if new_alias != alias:
        if not validate_alias(new_alias):
            print(_r(f"  ERROR: Invalid alias '{new_alias}'."))
            sys.exit(1)
        if new_alias in cfg["aliases"]:
            print(_r(f"  ERROR: Alias '{new_alias}' already exists."))
            sys.exit(1)
        remove_launcher(alias)
        del cfg["aliases"][alias]

    backup_config()
    cfg["aliases"][new_alias] = info
    save_config(cfg)

    target = info.get("target", "") if atype == "url" else info.get("script", "")
    write_launcher(new_alias, atype, target, info.get("interpreter", ""))

    label = f"'{alias}'" + (f" → '{new_alias}'" if new_alias != alias else "")
    print(_g(f"  OK  Updated {label}"))
    # pass a minimal args-like object to cmd_list
    class _LA:
        group = None
        json  = False
    cmd_list(_LA())


# ── rename (shortcut) ─────────────────────────────────────────────────────────
def cmd_rename(args):
    cfg = load_config()
    old = args.old_alias
    new = args.new_alias

    if old not in cfg["aliases"]:
        print(_r(f"  ERROR: Alias '{old}' not found."))
        sys.exit(1)
    if new in cfg["aliases"]:
        print(_r(f"  ERROR: Alias '{new}' already exists."))
        sys.exit(1)
    if not validate_alias(new):
        print(_r(f"  ERROR: Invalid alias name '{new}'."))
        sys.exit(1)
    if cfg["aliases"][old].get("locked"):
        print(_r(f"  ERROR: Alias '{old}' is locked. Run: shalias unfreeze {old}"))
        sys.exit(1)

    backup_config()
    info = cfg["aliases"].pop(old)
    cfg["aliases"][new] = info
    remove_launcher(old)
    atype  = info.get("type", "run")
    target = info.get("target", "") if atype == "url" else info.get("script", "")
    write_launcher(new, atype, target, info.get("interpreter", ""))
    save_config(cfg)
    print(_g(f"  OK  Renamed '{old}' → '{new}'"))


# ── run (invoke one or more aliases directly) ─────────────────────────────────
def cmd_run(args):
    """
    Run one or more aliases directly through shalias.
    Extra arguments after -- are forwarded to each run-type alias.
    """
    cfg        = load_config()
    alias_list = args.aliases
    extra_args = [a for a in (args.extra or []) if a != "--"]
    parallel   = getattr(args, "parallel", False)

    # Resolve all aliases up-front so we fail before launching anything
    resolved = []
    for alias in alias_list:
        if alias not in cfg["aliases"]:
            print(_r(f"  ERROR: Alias '{alias}' not found."))
            sys.exit(1)
        resolved.append((alias, cfg["aliases"][alias]))

    def _launch(alias, info):
        atype = info.get("type", "run")
        if atype == "run":
            interp       = info.get("interpreter", "")
            script       = info.get("script", "")
            interp_parts = interp.split() if interp else []
            cmd          = interp_parts + [script] + extra_args
        elif atype in ("open", "url"):
            if IS_LINUX:
                opener = "xdg-open"
            elif IS_MACOS:
                opener = "open"
            else:
                opener = "start"
            target = info.get("target", "") if atype == "url" else info.get("script", "")
            cmd    = ([opener, target] if not IS_WINDOWS
                      else ["cmd", "/c", "start", "", target])
        else:
            return 1

        result = subprocess.run(cmd)
        return result.returncode

    if len(resolved) == 1:
        alias, info = resolved[0]
        rc = _launch(alias, info)
        sys.exit(rc)

    # Multiple aliases
    if parallel:
        print(_c(f"\n  Running {len(resolved)} aliases in parallel...\n"))
        with ThreadPoolExecutor(max_workers=len(resolved)) as pool:
            futures = {pool.submit(_launch, a, i): a for a, i in resolved}
            results = {}
            for fut in as_completed(futures):
                a = futures[fut]
                try:
                    results[a] = fut.result()
                except Exception as exc:
                    results[a] = -1
                    print(_r(f"  ERROR: {a} raised {exc}"))
    else:
        print(_c(f"\n  Running {len(resolved)} aliases sequentially...\n"))
        results = {}
        for alias, info in resolved:
            print(_d(f"  → {alias}"))
            results[alias] = _launch(alias, info)

    print()
    any_fail = False
    for alias, rc in results.items():
        mark = _g("✓") if rc == 0 else _r("✗")
        print(f"  {mark}  {alias:<20} exit {rc}")
        if rc != 0:
            any_fail = True
    print()
    sys.exit(1 if any_fail else 0)


# ── run-group ─────────────────────────────────────────────────────────────────
def cmd_run_group(args):
    """Run every alias in a group at once."""
    cfg   = load_config()
    group = args.group

    members = {
        alias: info
        for alias, info in cfg.get("aliases", {}).items()
        if info.get("group", "") == group
    }

    if not members:
        print(_r(f"  ERROR: No aliases found in group '{group}'."))
        print("         Run 'shalias list' to see available groups.")
        sys.exit(1)

    print(_c(f"\n  Group '{group}' — {len(members)} alias(es)"))

    class _A:
        aliases  = list(members.keys())
        extra    = getattr(args, "extra", []) or []
        parallel = getattr(args, "parallel", False)

    cmd_run(_A())


# ── stats ─────────────────────────────────────────────────────────────────────
def cmd_stats(args):
    cfg     = load_config()
    aliases = cfg.get("aliases", {})

    if not aliases:
        print("\n  No aliases registered.\n")
        return

    by_use = sorted(aliases.items(), key=lambda kv: kv[1].get("use_count", 0), reverse=True)

    print()
    print(f"  {'ALIAS':<20} {'USES':>6}  {'LAST USED':<20}  BAR")
    print("  " + "─" * 65)
    for alias, info in by_use:
        uses     = info.get("use_count", 0)
        last_raw = info.get("last_used", "")
        if last_raw:
            try:
                dt   = datetime.fromisoformat(last_raw)
                last = dt.strftime("%Y-%m-%d %H:%M")
            except ValueError:
                last = last_raw[:16]
        else:
            last = _d("never")
        bar_len = min(uses, 30)
        bar     = _g("█" * bar_len)
        print(f"  {alias:<20} {str(uses):>6}  {last:<20}  {bar}")

    total_runs = sum(v.get("use_count", 0) for v in aliases.values())
    never_used = sum(1 for v in aliases.values() if not v.get("use_count", 0))
    print()
    print(f"  Total runs  : {total_runs}")
    print(f"  Never used  : {never_used} alias(es)")
    print()


# ── freeze / unfreeze ─────────────────────────────────────────────────────────
def cmd_freeze(args):
    cfg   = load_config()
    alias = args.alias
    if alias not in cfg["aliases"]:
        print(_r(f"  ERROR: Alias '{alias}' not found."))
        sys.exit(1)
    cfg["aliases"][alias]["locked"] = True
    save_config(cfg)
    print(_g(f"  OK  Alias '{alias}' is now locked (cannot be edited or removed)."))


def cmd_unfreeze(args):
    cfg   = load_config()
    alias = args.alias
    if alias not in cfg["aliases"]:
        print(_r(f"  ERROR: Alias '{alias}' not found."))
        sys.exit(1)
    cfg["aliases"][alias].pop("locked", None)
    save_config(cfg)
    print(_g(f"  OK  Alias '{alias}' is now unlocked."))


# ── update (self-update) ──────────────────────────────────────────────────────
def cmd_update(args):
    self_path = Path(sys.argv[0]).resolve()
    print(f"\n  Checking for updates... (current: v{VERSION})\n")

    try:
        req = urllib.request.Request(UPDATE_URL, method="GET")
        req.add_header("User-Agent", f"shalias/{VERSION}")
        with urllib.request.urlopen(req, timeout=10) as resp:
            remote_src = resp.read().decode("utf-8")
    except urllib.error.URLError as e:
        print(_r(f"  ERROR: Could not reach update server: {e}"))
        print("         Check your internet connection or update UPDATE_URL in the script.")
        sys.exit(1)

    m = re.search(r'^VERSION\s*=\s*["\']([^"\']+)["\']', remote_src, re.MULTILINE)
    if not m:
        print(_r("  ERROR: Could not parse remote version string."))
        sys.exit(1)

    remote_ver = m.group(1)
    if remote_ver == VERSION:
        print(_g(f"  Already up to date (v{VERSION})."))
        return

    print(f"  New version available: {_b('v' + remote_ver)}")
    ans = input("  Update now? [y/N] ").strip().lower()
    if ans != "y":
        print("  Cancelled.")
        return

    # Back up the current script
    backup = self_path.with_suffix(f".v{VERSION}.bak")
    shutil.copy2(self_path, backup)
    print(_d(f"  Backed up current version to: {backup}"))

    # Atomic replace
    fd, tmp = tempfile.mkstemp(dir=str(self_path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(remote_src)
        shutil.move(tmp, self_path)
    except Exception as e:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        print(_r(f"  ERROR: Failed to write update: {e}"))
        sys.exit(1)

    if not IS_WINDOWS:
        self_path.chmod(0o755)

    print(_g(f"  Updated to v{remote_ver}. Open a new terminal and run: shalias list"))


# ── export ────────────────────────────────────────────────────────────────────
def cmd_export(args):
    cfg      = load_config()
    warn_broken_aliases(cfg)
    out_path = Path(args.file).resolve()
    try:
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
        count = len(cfg.get("aliases", {}))
        print(_g(f"  OK  Exported {count} alias(es) to: {out_path}"))
    except IOError as e:
        print(_r(f"  ERROR: Could not write to {out_path}: {e}"))
        sys.exit(1)


# ── import ────────────────────────────────────────────────────────────────────
def cmd_import(args):
    in_path = Path(args.file).resolve()
    if not in_path.exists():
        print(_r(f"  ERROR: File not found: {in_path}"))
        sys.exit(1)
    try:
        with open(in_path, "r", encoding="utf-8") as f:
            imported = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(_r(f"  ERROR: Could not read {in_path}: {e}"))
        sys.exit(1)

    incoming = imported.get("aliases", {})
    if not incoming:
        print("  Nothing to import (no aliases found in file).")
        return

    dry_run = getattr(args, "dry_run", False)
    if dry_run:
        print(f"\n  Dry run — would import {len(incoming)} alias(es):\n")
        for alias in sorted(incoming):
            print(f"    {alias}")
        print()
        return

    cfg     = load_config()
    backup_config()
    added   = 0
    skipped = 0

    for alias, info in incoming.items():
        if alias in cfg["aliases"] and not args.overwrite:
            print(_y(f"  SKIP  '{alias}' already exists (use --overwrite to replace)"))
            skipped += 1
            continue

        atype  = info.get("type", "run")
        target = info.get("target", "") if atype == "url" else info.get("script", "")
        interp = info.get("interpreter", "")

        if atype != "url" and target and not Path(target).exists():
            print(_y(f"  WARN  '{alias}' — target missing on this machine: {target}"))

        cfg["aliases"][alias] = info
        write_launcher(alias, atype, target, interp)
        added += 1

    save_config(cfg)
    print(_g(f"  OK  Imported {added} alias(es), skipped {skipped}."))
    if skipped:
        print("      Re-run with --overwrite to replace existing aliases.")


# ── completion ────────────────────────────────────────────────────────────────
def cmd_completion(args):
    shell = args.shell.lower()
    cfg   = load_config()
    names = " ".join(sorted(cfg.get("aliases", {}).keys()))

    if shell == "bash":
        script = f"""\
# shalias bash completion — add to ~/.bashrc:
#   source <(shalias completion bash)
_shalias_complete() {{
    local cur="${{COMP_WORDS[COMP_CWORD]}}"
    local cmd="${{COMP_WORDS[1]}}"
    local cmds="install add remove list search doctor edit rename run run-group stats freeze unfreeze update export import config completion uninstall"
    local aliases="{names}"
    if [[ $COMP_CWORD -eq 1 ]]; then
        COMPREPLY=( $(compgen -W "$cmds" -- "$cur") )
    elif [[ "$cmd" =~ ^(remove|edit|rename|run|freeze|unfreeze)$ ]]; then
        COMPREPLY=( $(compgen -W "$aliases" -- "$cur") )
    fi
}}
complete -F _shalias_complete shalias
"""
    elif shell == "zsh":
        script = f"""\
# shalias zsh completion — add to ~/.zshrc:
#   source <(shalias completion zsh)
_shalias() {{
    local -a cmds aliases
    cmds=(install add remove list search doctor edit rename run run-group stats freeze unfreeze update export import config completion uninstall)
    aliases=({names})
    if (( CURRENT == 2 )); then
        _describe 'command' cmds
    else
        _describe 'alias' aliases
    fi
}}
compdef _shalias shalias
"""
    else:
        print(_r(f"  ERROR: Unsupported shell '{shell}'. Choose: bash, zsh"))
        sys.exit(1)

    print(script)


# ── config ────────────────────────────────────────────────────────────────────
def cmd_config(args):
    if not CONFIG_FILE.exists():
        save_config({"aliases": {}, "groups": {}, "meta": {}})
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
    print(_g("  OK  Removed from PATH and deleted all launchers."))
    print(_g(f"  OK  Config preserved at: {CONFIG_FILE}"))
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

  # Open / URL aliases
  shalias add notes.docx --alias notes --type open --group work
  shalias add https://github.com --alias gh --type url

  # Managing aliases
  shalias list
  shalias list --group devops
  shalias list --json
  shalias search github
  shalias doctor
  shalias doctor --fix

  # Edit (interactive if no flags given)
  shalias edit app
  shalias edit app --new-alias myapp
  shalias edit app --script /new/path/app.py
  shalias edit app --type open
  shalias edit app --group backend
  shalias edit app --group ""         # remove from group

  # Rename shortcut
  shalias rename old-name new-name

  # Run one or more aliases
  shalias run app
  shalias run build test deploy -- --verbose
  shalias run build test deploy --parallel

  # Run an entire group
  shalias run-group devops
  shalias run-group devops --parallel

  # Stats
  shalias stats

  # Lock / unlock
  shalias freeze important-alias
  shalias unfreeze important-alias

  # Self-update
  shalias update

  # Shell completion
  source <(shalias completion bash)
  source <(shalias completion zsh)

  # Portability
  shalias export backup.json
  shalias import backup.json
  shalias import backup.json --overwrite
  shalias import backup.json --dry-run

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
        help="Interpreter for the script (auto-detected from extension by default)")
    p_add.add_argument("--description",
        help="Optional note shown in 'shalias list'")
    p_add.add_argument("--group",
        help="Assign to a named group (e.g. devops, docs, finance)")

    # remove
    p_rem = sub.add_parser("remove",
        help="Unregister an alias and delete its launcher")
    p_rem.add_argument("alias", help="Alias name to remove")

    # list
    p_list = sub.add_parser("list", help="Show all registered aliases")
    p_list.add_argument("--group", help="Filter to a specific group")
    p_list.add_argument("--json",  action="store_true", help="Output raw JSON")

    # search
    p_search = sub.add_parser("search",
        help="Search aliases by name, description, target, group, or interpreter")
    p_search.add_argument("query", help="Search term")

    # doctor
    p_doc = sub.add_parser("doctor",
        help="Audit all aliases (missing files, broken interpreters, orphaned launchers)")
    p_doc.add_argument("--fix", action="store_true",
        help="Auto-remove aliases whose target files are missing")

    # edit
    p_edit = sub.add_parser("edit",
        help="Modify an existing alias (interactive if no flags given)")
    p_edit.add_argument("alias",         help="Alias to modify")
    p_edit.add_argument("--new-alias",   dest="new_alias",  help="Rename the alias")
    p_edit.add_argument("--script",      help="Point to a different file or URL")
    p_edit.add_argument("--type",        choices=ALIAS_TYPES, help="Change the alias type")
    p_edit.add_argument("--interpreter", help="Change the interpreter (run type only)")
    p_edit.add_argument("--description", help="Update description (pass '' to clear)")
    p_edit.add_argument("--group",       help="Change group (pass '' to remove from group)")

    # rename
    p_ren = sub.add_parser("rename",
        help="Rename an alias (shortcut for edit --new-alias)")
    p_ren.add_argument("old_alias", help="Current alias name")
    p_ren.add_argument("new_alias", help="New alias name")

    # run
    p_run = sub.add_parser("run",
        help="Run one or more aliases directly (extra args after --)")
    p_run.add_argument("aliases", nargs="+", help="Alias name(s) to run")
    p_run.add_argument("--parallel", action="store_true",
        help="Run all aliases simultaneously")
    p_run.add_argument("extra", nargs=argparse.REMAINDER,
        help="Extra arguments forwarded to the script(s) (after --)")

    # run-group
    p_rg = sub.add_parser("run-group",
        help="Run every alias in a group")
    p_rg.add_argument("group", help="Group name")
    p_rg.add_argument("--parallel", action="store_true",
        help="Run all aliases in the group simultaneously")
    p_rg.add_argument("extra", nargs=argparse.REMAINDER,
        help="Extra arguments forwarded to run-type scripts")

    # stats
    sub.add_parser("stats", help="Show usage statistics for all aliases")

    # freeze / unfreeze
    p_freeze = sub.add_parser("freeze",
        help="Lock an alias to prevent accidental edits or removal")
    p_freeze.add_argument("alias", help="Alias to lock")
    p_unfreeze = sub.add_parser("unfreeze", help="Unlock a frozen alias")
    p_unfreeze.add_argument("alias", help="Alias to unlock")

    # update
    sub.add_parser("update",
        help="Check for and install the latest version of shalias")

    # export
    p_exp = sub.add_parser("export",
        help="Export all aliases to a JSON file (backup / portability)")
    p_exp.add_argument("file", help="Output path (e.g. backup.json)")

    # import
    p_imp = sub.add_parser("import",
        help="Import aliases from a previously exported JSON file")
    p_imp.add_argument("file", help="Input path")
    p_imp.add_argument("--overwrite", action="store_true",
        help="Replace existing aliases that share the same name")
    p_imp.add_argument("--dry-run", dest="dry_run", action="store_true",
        help="Preview what would be imported without making any changes")

    # completion
    p_comp = sub.add_parser("completion",
        help="Print shell completion script (bash or zsh)")
    p_comp.add_argument("shell", choices=["bash", "zsh"], help="Target shell")

    # config
    sub.add_parser("config", help="Open config.json in your default editor")

    # uninstall
    sub.add_parser("uninstall",
        help="Remove shalias from PATH and delete all launchers")

    # _track — internal, called from generated launchers
    p_track = sub.add_parser("_track")
    p_track.add_argument("alias")

    args = parser.parse_args()
    {
        "install":    cmd_install,
        "add":        cmd_add,
        "remove":     cmd_remove,
        "list":       cmd_list,
        "search":     cmd_search,
        "doctor":     cmd_doctor,
        "edit":       cmd_edit,
        "rename":     cmd_rename,
        "run":        cmd_run,
        "run-group":  cmd_run_group,
        "stats":      cmd_stats,
        "freeze":     cmd_freeze,
        "unfreeze":   cmd_unfreeze,
        "update":     cmd_update,
        "export":     cmd_export,
        "import":     cmd_import,
        "completion": cmd_completion,
        "config":     cmd_config,
        "uninstall":  cmd_uninstall,
        "_track":     cmd_track,
    }[args.command](args)


if __name__ == "__main__":
    main()
