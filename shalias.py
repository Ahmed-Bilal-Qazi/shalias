#!/usr/bin/env python3
"""
shalias — Cross-Platform Script Alias Manager  v3.0

Changelog
─────────
3.0  Auto-detect alias type · alias chaining (shalias chain) · env var
     injection (--env) · inline shell commands (--inline) · clone command ·
     --cwd working directory per alias · instant list (removed 4s network
     block) · broken-alias check is now opt-in (--check) · cleaner code

2.0  Parallel execution · groups · usage stats · locking · JSON output ·
     dry-run import · background auto-update · shell autocompletion · doctor

1.0  Initial release

Quick start
───────────
  python shalias.py install                       # one-time setup
  shalias add myscript.py                         # type auto-detected
  shalias add https://github.com --alias gh       # URL alias
  shalias add "git log --oneline -10" --alias gl --inline
  shalias chain morning --run coffee news standup
  shalias list
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
from concurrent.futures import ThreadPoolExecutor

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
VERSION     = "3.0"

UPDATE_URL = "https://raw.githubusercontent.com/Ahmed-Bilal-Qazi/shalias/main/shalias.py"

BANNER = r"""
  _____ _           _ _
 / ____| |         | (_)
| (___ | |__   __ _| |_  __ _ ___
 \___ \| '_ \ / _` | | |/ _` / __|
 ____) | | | | (_| | | | (_| \__ \
|_____/|_| |_|\__,_|_|_|\__,_|___/

  Cross-Platform Script Alias Manager  v3.0
"""

ALIAS_TYPES = ("run", "open", "url", "inline", "chain")

INTERPRETER_MAP = {
    ".py":  "python3" if not IS_WINDOWS else "python",
    ".js":  "node",
    ".ts":  "ts-node",
    ".rb":  "ruby",
    ".pl":  "perl",
    ".sh":  "bash",
    ".ps1": "powershell",
    ".lua": "lua",
    ".php": "php",
    ".r":   "Rscript",
    ".R":   "Rscript",
    ".go":  "go run",
}

# These extensions open with the system default app rather than a interpreter
OPEN_EXTENSIONS = {
    ".pdf", ".docx", ".doc", ".xlsx", ".xls", ".pptx", ".ppt",
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".mp4", ".mp3",
    ".zip", ".tar", ".gz", ".csv",
}

# ── Colors ────────────────────────────────────────────────────────────────────

_USE_COLOR = None

def _use_color():
    global _USE_COLOR
    if _USE_COLOR is None:
        _USE_COLOR = sys.stdout.isatty() and not os.environ.get("NO_COLOR")
    return _USE_COLOR

COLORS = {
    "green":  "\033[32m",
    "yellow": "\033[33m",
    "red":    "\033[31m",
    "cyan":   "\033[36m",
    "bold":   "\033[1m",
    "dim":    "\033[2m",
    "reset":  "\033[0m",
}

def _col(name, s):
    return f"{COLORS[name]}{s}{COLORS['reset']}" if _use_color() else s

def _g(s):  return _col("green",  s)
def _y(s):  return _col("yellow", s)
def _r(s):  return _col("red",    s)
def _b(s):  return _col("bold",   s)
def _d(s):  return _col("dim",    s)
def _cy(s): return _col("cyan",   s)

# ── Config ────────────────────────────────────────────────────────────────────

def load_config() -> dict:
    if not CONFIG_FILE.exists():
        return {"aliases": {}, "groups": {}, "meta": {}}
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        data.setdefault("aliases", {})
        data.setdefault("groups",  {})
        data.setdefault("meta",    {})
        return data
    except (json.JSONDecodeError, IOError):
        print(_y("  config.json looks corrupted — starting fresh."))
        print(_y("  Your backups are in ~/.shalias/backups/ if you need them."))
        return {"aliases": {}, "groups": {}, "meta": {}}


def save_config(cfg: dict):
    SHALIAS_DIR.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(SHALIAS_DIR), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
        shutil.move(tmp, CONFIG_FILE)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def backup_config():
    if not CONFIG_FILE.exists():
        return
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    ts  = datetime.now().strftime("%Y%m%d_%H%M%S")
    dst = BACKUP_DIR / f"config_{ts}.json"
    shutil.copy2(CONFIG_FILE, dst)
    # keep the 10 most recent, quietly drop the rest
    for old in sorted(BACKUP_DIR.glob("config_*.json"), reverse=True)[10:]:
        try:
            old.unlink()
        except OSError:
            pass

# ── PATH management — Windows ─────────────────────────────────────────────────

def _win_get_user_path() -> list:
    r = subprocess.run(
        ["reg", "query", "HKCU\\Environment", "/v", "PATH"],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        return []
    for line in r.stdout.splitlines():
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
    r = subprocess.run(
        ["reg", "add", "HKCU\\Environment", "/v", "PATH",
         "/t", "REG_EXPAND_SZ", "/d", ";".join(clean), "/f"],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        print(_r(f"  Couldn't write PATH to registry: {r.stderr.strip()}"))
        sys.exit(1)
    subprocess.run(["setx", "_SHALIAS_REFRESH", "1"], capture_output=True)
    subprocess.run(
        ["reg", "delete", "HKCU\\Environment", "/v", "_SHALIAS_REFRESH", "/f"],
        capture_output=True,
    )


def _win_add_to_path(entry: str):
    entries = _win_get_user_path()
    if entry.lower() not in [e.lower() for e in entries]:
        entries.append(entry)
        _win_set_user_path(entries)
        print(_g(f"  Added to PATH: {entry}"))
    else:
        print(_g(f"  Already in PATH: {entry}"))


def _win_remove_from_path(entry: str):
    entries = _win_get_user_path()
    cleaned = [e for e in entries if e.lower() != entry.lower()]
    if len(cleaned) < len(entries):
        _win_set_user_path(cleaned)
        print(_g(f"  Removed from PATH: {entry}"))

# ── PATH management — Unix ────────────────────────────────────────────────────

def _unix_shell_configs() -> list:
    candidates = [
        ".bashrc", ".zshrc", ".profile", ".bash_profile",
        ".config/fish/config.fish",
    ]
    return [HOME / f for f in candidates if (HOME / f).exists()]


def _unix_add_to_path():
    line   = f'export PATH="{BIN_DIR}:$PATH"  # shalias'
    marker = str(BIN_DIR)
    configs = _unix_shell_configs() or [HOME / ".bashrc"]
    for rc in configs:
        try:
            content = rc.read_text(encoding="utf-8") if rc.exists() else ""
            if marker not in content:
                with open(rc, "a", encoding="utf-8") as f:
                    f.write(f"\n{line}\n")
                print(_g(f"  PATH entry added to {rc}"))
            else:
                print(_g(f"  Already in PATH ({rc})"))
        except IOError as e:
            print(_y(f"  Couldn't write to {rc}: {e}"))


def _unix_remove_from_path():
    marker = str(BIN_DIR)
    for rc in _unix_shell_configs():
        try:
            content = rc.read_text(encoding="utf-8")
            if marker in content:
                cleaned = "\n".join(
                    ln for ln in content.splitlines() if marker not in ln
                ).strip() + "\n"
                rc.write_text(cleaned, encoding="utf-8")
                print(_g(f"  Removed PATH entry from {rc}"))
        except IOError as e:
            print(_y(f"  Couldn't update {rc}: {e}"))

# ── Unified PATH API ──────────────────────────────────────────────────────────

def add_to_path():
    if IS_WINDOWS:
        _win_add_to_path(str(BIN_DIR))
    else:
        _unix_add_to_path()


def remove_from_path():
    if IS_WINDOWS:
        _win_remove_from_path(str(BIN_DIR))
    else:
        _unix_remove_from_path()

# ── Launcher generation ───────────────────────────────────────────────────────

def _env_lines_unix(env: dict) -> str:
    if not env:
        return ""
    return "".join(f'export {k}="{v}"\n' for k, v in env.items())


def _env_lines_win(env: dict) -> str:
    if not env:
        return ""
    return "".join(f"set {k}={v}\n" for k, v in env.items())


def _cwd_line_unix(cwd: str, script_path: str) -> str:
    if not cwd or cwd == "current":
        return ""
    if cwd == "script":
        return f'cd "{Path(script_path).parent}"\n' if script_path else ""
    return f'cd "{cwd}"\n'


def _cwd_line_win(cwd: str, script_path: str) -> str:
    if not cwd or cwd == "current":
        return ""
    if cwd == "script":
        return f'cd /d "{Path(script_path).parent}"\n' if script_path else ""
    return f'cd /d "{cwd}"\n'


def write_launcher(alias: str, entry: dict) -> Path:
    BIN_DIR.mkdir(parents=True, exist_ok=True)

    atype      = entry.get("type", "run")
    target     = entry.get("target") or entry.get("script", "")
    interp     = entry.get("interpreter", "")
    env        = entry.get("env", {})
    cwd        = entry.get("cwd", "")
    chain_list = entry.get("chain", [])

    self_path = Path(sys.argv[0]).resolve()
    py        = sys.executable

    if IS_WINDOWS:
        launcher_path = BIN_DIR / f"{alias}.bat"
        track = f'"{py}" "{self_path}" _track {alias} 2>nul\n'
        env_b = _env_lines_win(env)

        if atype == "run":
            cwd_b = _cwd_line_win(cwd, target)
            body  = f'"{interp}" "{target}" %*\n'
        elif atype == "inline":
            cwd_b = _cwd_line_win(cwd, "") if cwd not in ("", "current", "script") else ""
            body  = f"{target} %*\n"
        elif atype in ("open", "url"):
            cwd_b = ""
            body  = f'start "" "{target}"\n'
        elif atype == "chain":
            cwd_b = ""
            body  = "\n".join(
                f'call "{BIN_DIR / (a + ".bat")}"' for a in chain_list
            ) + "\n"
        else:
            raise ValueError(f"Unknown alias type: {atype}")

        content = f"@echo off\n{track}{env_b}{cwd_b}{body}"
        launcher_path.write_text(content, encoding="utf-8")

    else:
        launcher_path = BIN_DIR / alias
        track  = f'"{py}" "{self_path}" _track {alias} 2>/dev/null &\n'
        env_b  = _env_lines_unix(env)
        opener = "xdg-open" if IS_LINUX else "open"

        if atype == "run":
            cwd_b = _cwd_line_unix(cwd, target)
            body  = f'"{interp}" "{target}" "$@"\n'
        elif atype == "inline":
            cwd_b = _cwd_line_unix(cwd, "") if cwd not in ("", "current", "script") else ""
            body  = f'{target} "$@"\n'
        elif atype == "open":
            cwd_b = ""
            body  = f'{opener} "{target}"\n'
        elif atype == "url":
            cwd_b = ""
            body  = f'{opener} "{target}"\n'
        elif atype == "chain":
            cwd_b = ""
            body  = "\n".join(f'"{BIN_DIR / a}"' for a in chain_list) + "\n"
        else:
            raise ValueError(f"Unknown alias type: {atype}")

        content = f"#!/usr/bin/env bash\n{track}{env_b}{cwd_b}{body}"
        launcher_path.write_text(content, encoding="utf-8")
        launcher_path.chmod(0o755)

    return launcher_path


def remove_launcher(alias: str):
    for name in [alias, f"{alias}.bat"]:
        p = BIN_DIR / name
        if p.exists():
            p.unlink()

# ── Type / interpreter detection ──────────────────────────────────────────────

def detect_type(target: str) -> str:
    if target.startswith("http://") or target.startswith("https://"):
        return "url"
    suffix = Path(target).suffix.lower()
    if suffix in INTERPRETER_MAP:
        return "run"
    if suffix in OPEN_EXTENSIONS:
        return "open"
    return "run"  # unknown extension — try running it


def detect_interpreter(script_path: Path) -> str:
    return INTERPRETER_MAP.get(
        script_path.suffix.lower(),
        "python3" if not IS_WINDOWS else "python",
    )

# ── Validators ────────────────────────────────────────────────────────────────

_SAFE_NAME = re.compile(r"^[A-Za-z0-9_-]+$")


def validate_alias(name: str) -> bool:
    return bool(name) and bool(_SAFE_NAME.match(name))


def validate_group(name: str) -> bool:
    return bool(name) and bool(_SAFE_NAME.match(name))


def validate_url(target: str) -> bool:
    return target.startswith("http://") or target.startswith("https://")


def parse_env(env_list: list) -> dict:
    result = {}
    for item in (env_list or []):
        if "=" not in item:
            print(_y(f"  Skipping malformed --env value '{item}' — expected KEY=VALUE"))
            continue
        k, _, v = item.partition("=")
        result[k.strip()] = v.strip()
    return result


def _check_alias_free(alias: str, cfg: dict):
    if not validate_alias(alias):
        print(_r(f"  '{alias}' isn't a valid name."))
        print("  Use only letters, numbers, hyphens (-), and underscores (_).")
        sys.exit(1)
    if alias in cfg["aliases"]:
        print(_r(f"  '{alias}' already exists."))
        print(f"  To change it: shalias edit {alias}")
        sys.exit(1)

# ── Background update check ───────────────────────────────────────────────────

def _check_update_async(cfg: dict):
    meta = cfg.setdefault("meta", {})
    if time.time() - meta.get("last_update_check", 0) < 86400:
        return

    def _do():
        try:
            req = urllib.request.Request(UPDATE_URL, method="GET")
            req.add_header("User-Agent", f"shalias/{VERSION}")
            with urllib.request.urlopen(req, timeout=4) as resp:
                src = resp.read(4096).decode("utf-8", errors="ignore")
            m = re.search(r'^VERSION\s*=\s*["\']([^"\']+)["\']', src, re.MULTILINE)
            if m and m.group(1) != VERSION:
                print(_y(
                    f"\n  shalias {m.group(1)} is available"
                    f" (you have {VERSION}). Run: shalias update\n"
                ))
        except Exception:
            pass
        meta["last_update_check"] = time.time()
        try:
            save_config(cfg)
        except Exception:
            pass

    # Fully async — never blocks the CLI
    threading.Thread(target=_do, daemon=True).start()

# ── Usage tracking (called from generated launchers) ─────────────────────────

def cmd_track(args):
    try:
        cfg = load_config()
        e = cfg["aliases"].get(args.alias)
        if e:
            e["use_count"] = e.get("use_count", 0) + 1
            e["last_used"] = datetime.now(timezone.utc).isoformat()
            save_config(cfg)
    except Exception:
        pass  # tracking failures must never surface to the user

# ── Alias summary printer ─────────────────────────────────────────────────────

def _print_alias_summary(alias: str, entry: dict, launcher: Path):
    atype = entry.get("type", "run")
    print()
    print(_g(f"  ✓ {alias}"))
    print(f"    type        : {atype}")
    if atype == "chain":
        print(f"    runs        : {' → '.join(entry.get('chain', []))}")
    elif atype in ("url", "inline"):
        print(f"    target      : {entry.get('target', '')}")
    else:
        print(f"    script      : {entry.get('script', '')}")
        if atype == "run":
            print(f"    interpreter : {entry.get('interpreter', '')}")
    if entry.get("env"):
        print(f"    env         : {' '.join(f'{k}={v}' for k, v in entry['env'].items())}")
    if entry.get("cwd"):
        print(f"    cwd         : {entry['cwd']}")
    if entry.get("group"):
        print(f"    group       : {entry['group']}")
    if entry.get("description"):
        print(f"    description : {entry['description']}")
    print(f"    launcher    : {launcher}")
    suffix = " [args...]" if atype in ("run", "inline") else ""
    print(f"\n  Run it from anywhere: {_b(alias)}{suffix}\n")

# ══════════════════════════════════════════════════════════════════════════════
# Commands
# ══════════════════════════════════════════════════════════════════════════════

def cmd_install(args):
    print(BANNER)
    print(f"  Platform : {PLATFORM} ({platform.release()})")
    print(f"  Home     : {HOME}")
    print(f"  Install  : {SHALIAS_DIR}")
    print()

    SHALIAS_DIR.mkdir(parents=True, exist_ok=True)
    BIN_DIR.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    self_path = Path(sys.argv[0]).resolve()
    if not self_path.exists() or self_path.suffix.lower() != ".py":
        print(_r(f"  Can't find shalias.py at {self_path}"))
        print("  Run it as: python shalias.py install")
        sys.exit(1)

    interp = "python" if IS_WINDOWS else "python3"
    shalias_entry = {
        "type": "run", "script": str(self_path), "interpreter": interp,
        "description": "shalias itself", "use_count": 0, "env": {}, "cwd": "",
    }
    launcher = write_launcher("shalias", shalias_entry)
    print(_g(f"  Launcher : {launcher}"))
    print(_g(f"  Points to: {self_path}"))

    add_to_path()

    if not CONFIG_FILE.exists():
        save_config({"aliases": {}, "groups": {}, "meta": {}})
    print(_g(f"  Config   : {CONFIG_FILE}"))
    print()

    if IS_WINDOWS:
        print("  All set! Open a new cmd window and try: shalias list")
    else:
        print("  All set! Reload your shell, then try: shalias list")
        for rc in _unix_shell_configs():
            print(f"    source {rc}")
    print()


def cmd_add(args):
    cfg = load_config()
    _check_update_async(cfg)

    # ── inline command ────────────────────────────────────────────────────────
    if getattr(args, "inline", False):
        alias = args.alias
        if not alias:
            print(_r("  --alias is required for inline commands."))
            sys.exit(1)
        _check_alias_free(alias, cfg)
        entry = {
            "type":        "inline",
            "target":      args.script,
            "description": args.description or "",
            "env":         parse_env(getattr(args, "env", None) or []),
            "cwd":         getattr(args, "cwd", "") or "",
            "use_count":   0,
        }
        if getattr(args, "group", None):
            entry["group"] = args.group
        cfg["aliases"][alias] = entry
        save_config(cfg)
        launcher = write_launcher(alias, entry)
        _print_alias_summary(alias, entry, launcher)
        return

    # ── auto-detect type ──────────────────────────────────────────────────────
    raw   = args.script
    atype = (getattr(args, "type", None) or detect_type(raw)).lower()

    if atype not in ALIAS_TYPES:
        print(_r(f"  Unknown type '{atype}'. Options: {', '.join(ALIAS_TYPES)}"))
        sys.exit(1)

    group = (getattr(args, "group", None) or "").strip()
    if group and not validate_group(group):
        print(_r(f"  Invalid group name '{group}'."))
        print("  Letters, numbers, hyphens, and underscores only.")
        sys.exit(1)

    # ── URL ───────────────────────────────────────────────────────────────────
    if atype == "url":
        if not validate_url(raw):
            print(_r(f"  Doesn't look like a URL: {raw}"))
            print("  URLs need to start with http:// or https://")
            sys.exit(1)
        alias = args.alias
        if not alias:
            print(_r("  --alias is required for URL aliases."))
            sys.exit(1)
        _check_alias_free(alias, cfg)
        entry = {
            "type": "url", "target": raw,
            "description": args.description or "",
            "use_count": 0, "env": {}, "cwd": "",
        }
        if group:
            entry["group"] = group
        cfg["aliases"][alias] = entry
        save_config(cfg)
        launcher = write_launcher(alias, entry)
        _print_alias_summary(alias, entry, launcher)
        return

    # ── file-based (run / open) ───────────────────────────────────────────────
    script = Path(raw).resolve()
    if not script.exists():
        print(_r(f"  File not found: {script}"))
        if " " in raw:
            print(f'  Tip: quote paths with spaces: shalias add "{raw}" ...')
        elif not Path(raw).suffix:
            print("  If this is a shell command, use --inline instead.")
        sys.exit(1)

    alias = args.alias or script.stem
    _check_alias_free(alias, cfg)

    base = {
        "description": args.description or "",
        "use_count":   0,
        "env":         parse_env(getattr(args, "env", None) or []),
        "cwd":         getattr(args, "cwd", "") or "",
    }
    if group:
        base["group"] = group

    if atype == "open":
        entry = {**base, "type": "open", "script": str(script)}
    else:
        interp = getattr(args, "interpreter", None) or detect_interpreter(script)
        entry  = {**base, "type": "run", "script": str(script), "interpreter": interp}

    cfg["aliases"][alias] = entry
    save_config(cfg)
    launcher = write_launcher(alias, entry)
    _print_alias_summary(alias, entry, launcher)


def cmd_chain(args):
    cfg   = load_config()
    name  = args.name
    steps = args.run

    _check_alias_free(name, cfg)

    missing = [s for s in steps if s not in cfg["aliases"]]
    if missing:
        print(_r(f"  These aliases don't exist yet: {', '.join(missing)}"))
        print("  Add them first, then chain them.")
        sys.exit(1)

    entry = {
        "type":        "chain",
        "chain":       steps,
        "description": args.description or "",
        "use_count":   0,
        "env":         {},
        "cwd":         "",
    }
    if getattr(args, "group", None):
        entry["group"] = args.group
    cfg["aliases"][name] = entry
    save_config(cfg)
    launcher = write_launcher(name, entry)
    _print_alias_summary(name, entry, launcher)


def cmd_clone(args):
    cfg = load_config()
    src = args.source
    dst = args.dest

    if src not in cfg["aliases"]:
        print(_r(f"  '{src}' doesn't exist. Nothing to clone."))
        sys.exit(1)
    _check_alias_free(dst, cfg)

    entry = dict(cfg["aliases"][src])
    entry["use_count"] = 0
    entry.pop("last_used", None)

    cfg["aliases"][dst] = entry
    save_config(cfg)
    launcher = write_launcher(dst, entry)
    print(_g(f"\n  ✓ Cloned '{src}' → '{dst}'"))
    print(f"    Tweak it with: shalias edit {dst}\n")


def cmd_remove(args):
    cfg   = load_config()
    alias = args.alias

    if alias not in cfg["aliases"]:
        print(_r(f"  '{alias}' not found. Try: shalias list"))
        sys.exit(1)
    if cfg["aliases"][alias].get("locked"):
        print(_r(f"  '{alias}' is locked. Unlock it first: shalias unfreeze {alias}"))
        sys.exit(1)

    backup_config()
    remove_launcher(alias)
    del cfg["aliases"][alias]
    save_config(cfg)
    print(_g(f"  ✓ Removed '{alias}'"))


def cmd_list(args):
    cfg = load_config()
    _check_update_async(cfg)

    aliases      = cfg.get("aliases", {})
    group_filter = getattr(args, "group", None)
    sort_by      = getattr(args, "sort",  None)
    json_out     = getattr(args, "json",  False)
    check        = getattr(args, "check", False)

    if group_filter:
        aliases = {k: v for k, v in aliases.items()
                   if v.get("group", "") == group_filter}

    if sort_by == "recent":
        aliases = dict(sorted(aliases.items(),
                              key=lambda x: x[1].get("last_used", ""), reverse=True))
    elif sort_by == "uses":
        aliases = dict(sorted(aliases.items(),
                              key=lambda x: x[1].get("use_count", 0), reverse=True))
    else:
        aliases = dict(sorted(aliases.items()))

    # Broken-alias check is opt-in — keeps list instant
    if check:
        broken = [
            (a, i.get("script", ""))
            for a, i in aliases.items()
            if i.get("type") == "run" and not Path(i.get("script", "x")).exists()
        ]
        if broken:
            print()
            print(_y("  Some aliases point to missing files:"))
            for a, t in broken:
                print(f"    {a:<20} → {t}")
            print("  Run 'shalias doctor' for the full breakdown.\n")

    if not aliases:
        print()
        if group_filter:
            print(f"  No aliases in group '{group_filter}'.")
        else:
            print("  Nothing registered yet.")
            print("  Add a script  : shalias add myscript.py")
            print("  Add a URL     : shalias add https://example.com --alias ex")
            print("  Inline command: shalias add 'git log --oneline -5' --alias gl --inline")
        print()
        return

    if json_out:
        print(json.dumps(aliases, indent=2))
        return

    grouped   = {}
    ungrouped = {}
    for alias, info in aliases.items():
        g = info.get("group", "")
        if g:
            grouped.setdefault(g, {})[alias] = info
        else:
            ungrouped[alias] = info

    header  = f"  {'ALIAS':<20} {'TYPE':<8} {'STATUS':<8} {'USES':<6} {'GROUP':<14} DESCRIPTION / TARGET"
    divider = "  " + "─" * 95

    def _row(alias, info):
        atype = info.get("type", "run")
        desc  = info.get("description", "") or ""
        grp   = info.get("group", "")
        uses  = str(info.get("use_count", 0))
        lock  = " 🔒" if info.get("locked") else ""

        if atype in ("url", "inline"):
            target = info.get("target", "")
        elif atype == "chain":
            target = " → ".join(info.get("chain", []))
        else:
            target = info.get("script", "")

        ok     = atype in ("url", "inline", "chain") or Path(target).exists()
        status = _g("ok") if ok else _r("missing")
        label  = desc[:30] if desc else _d(target[:40])

        # pad status accounting for invisible color codes
        raw_status = "ok" if ok else "missing"
        pad = " " * max(0, 8 - len(raw_status))
        print(f"  {alias + lock:<20} {atype:<8} {status}{pad} {uses:<6} {grp:<14} {label}")

    print()
    print(_b(header))
    print(divider)
    for alias, info in ungrouped.items():
        _row(alias, info)
    for grp_name, members in sorted(grouped.items()):
        if ungrouped:
            print()
        print(_cy(f"  [{grp_name}]"))
        for alias, info in sorted(members.items()):
            _row(alias, info)

    total = len(aliases)
    print()
    print(_d(
        f"  {total} alias{'es' if total != 1 else ''}"
        "  ·  shalias search <term>"
        "  ·  shalias list --check"
        "  ·  shalias doctor"
    ))
    print()


def cmd_search(args):
    cfg   = load_config()
    query = args.query.lower().strip()

    if not query:
        print(_r("  Search query can't be empty."))
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
        print(f"\n  No results for '{args.query}'.\n")
        return

    print(f"\n  {len(found)} result(s) for '{_b(args.query)}':\n")
    print(f"  {'ALIAS':<20} {'TYPE':<8} {'USES':<6} {'GROUP':<14} TARGET / DESCRIPTION")
    print("  " + "─" * 85)
    for alias, info in sorted(found.items()):
        atype  = info.get("type", "run")
        desc   = info.get("description", "") or ""
        grp    = info.get("group", "")
        uses   = str(info.get("use_count", 0))
        target = info.get("target", "") if atype in ("url", "inline") else info.get("script", "")
        label  = desc[:30] if desc else _d(target[:40])
        print(f"  {alias:<20} {atype:<8} {uses:<6} {grp:<14} {label}")
    print()


def cmd_doctor(args):
    cfg     = load_config()
    aliases = cfg.get("aliases", {})
    do_fix  = getattr(args, "fix", False)

    if not aliases:
        print("\n  No aliases registered — nothing to check.\n")
        return

    ok_count = missing_count = warning_count = fixed_count = 0
    to_remove = []

    print("\n  Running diagnostics...\n")
    print(f"  {'ALIAS':<20} {'STATUS':<14} DETAIL")
    print("  " + "─" * 80)

    for alias, info in sorted(aliases.items()):
        atype    = info.get("type", "run")
        target   = info.get("target", "") if atype in ("url", "inline") else info.get("script", "")
        launcher = BIN_DIR / (f"{alias}.bat" if IS_WINDOWS else alias)

        if not launcher.exists():
            print(f"  {alias:<20} {_y('no launcher'):<22}  re-add, or run: shalias doctor --fix")
            warning_count += 1
            continue

        if atype in ("url", "inline", "chain"):
            detail = target[:50] if target else str(info.get("chain", []))
            print(f"  {alias:<20} {_g('ok'):<22}  {_d(detail)}")
            ok_count += 1
            continue

        if not target:
            print(f"  {alias:<20} {_r('no target'):<22}  no script path in config")
            warning_count += 1
            continue

        if not Path(target).exists():
            missing_count += 1
            if do_fix:
                to_remove.append(alias)
                print(f"  {alias:<20} {_r('removed'):<22}  {_d(target)}")
                fixed_count += 1
            else:
                print(f"  {alias:<20} {_r('missing'):<22}  {_d(target)}")
            continue

        if atype == "run":
            interp_bin = (info.get("interpreter", "") or "").split()[0]
            if interp_bin and not shutil.which(interp_bin):
                print(f"  {alias:<20} {_y('no interpreter'):<22}  '{interp_bin}' not found in PATH")
                warning_count += 1
                continue

        print(f"  {alias:<20} {_g('ok'):<22}  {_d(target)}")
        ok_count += 1

    if do_fix and to_remove:
        backup_config()
        for alias in to_remove:
            remove_launcher(alias)
            del cfg["aliases"][alias]
        save_config(cfg)

    total = len(aliases)
    print()
    print("  ── Summary " + "─" * 40)
    print(f"  Checked      : {total}")
    print(f"  {_g('OK')}          : {ok_count}")
    print(f"  Missing      : {missing_count}")
    print(f"  Warnings     : {warning_count}")
    if do_fix:
        print(f"  Fixed        : {fixed_count}")
    if (missing_count or warning_count) and not do_fix:
        print()
        print("  Fix script path  : shalias edit <alias> --script <new-path>")
        print("  Fix interpreter  : shalias edit <alias> --interpreter <cmd>")
        print("  Remove broken    : shalias doctor --fix")
    print()


def cmd_edit(args):
    cfg   = load_config()
    alias = args.alias

    if alias not in cfg["aliases"]:
        print(_r(f"  '{alias}' not found. Try: shalias list"))
        sys.exit(1)
    if cfg["aliases"][alias].get("locked"):
        print(_r(f"  '{alias}' is locked. Unlock with: shalias unfreeze {alias}"))
        sys.exit(1)

    info  = dict(cfg["aliases"][alias])
    atype = info.get("type", "run")

    # Interactive mode when no field flags are given
    field_flags = [
        getattr(args, "new_alias",    None),
        getattr(args, "script",       None),
        getattr(args, "interpreter",  None),
        getattr(args, "description",  None),
        getattr(args, "group",        None),
        getattr(args, "type",         None),
    ]
    interactive = not any(f is not None for f in field_flags)

    if interactive:
        print(f"\n  Editing: {_b(alias)}")
        print(_d("  Hit Enter to keep the current value. Space + Enter to clear a field.\n"))

        def _prompt(label, current):
            val = input(f"  {label:<16} [{current}]: ").strip()
            if val == " ":
                return ""
            return val if val else current

        new_alias_i = _prompt("alias name", alias)

        new_type_i = atype
        while True:
            nt = _prompt(f"type", atype)
            if nt in ALIAS_TYPES:
                new_type_i = nt
                break
            elif nt == atype:
                break
            print(_y(f"  Options: {', '.join(ALIAS_TYPES)}"))

        if new_type_i in ("url", "inline"):
            new_script_i = _prompt("target", info.get("target", ""))
        else:
            new_script_i = _prompt("script path", info.get("script", ""))

        new_interp_i = ""
        if new_type_i == "run":
            new_interp_i = _prompt("interpreter", info.get("interpreter", ""))

        new_desc_raw = input(f"  {'description':<16} [{info.get('description', '')}]: ").strip()
        new_desc     = new_desc_raw if new_desc_raw else info.get("description", "")
        if new_desc_raw == " ":
            new_desc = ""

        new_group_raw = input(f"  {'group':<16} [{info.get('group', '') or 'none'}]: ").strip()
        new_group     = new_group_raw if new_group_raw else info.get("group", "")
        if new_group_raw == " ":
            new_group = ""

        new_cwd_raw = input(f"  {'cwd':<16} [{info.get('cwd', '') or 'none'}]: ").strip()
        new_cwd     = new_cwd_raw if new_cwd_raw else info.get("cwd", "")
        if new_cwd_raw == " ":
            new_cwd = ""

        print()
        src_target = info.get("script", info.get("target", ""))
        args.new_alias   = new_alias_i  if new_alias_i  != alias        else None
        args.type        = new_type_i   if new_type_i   != atype         else None
        args.script      = new_script_i if new_script_i != src_target    else None
        args.interpreter = new_interp_i if new_interp_i != info.get("interpreter", "") else None
        args.description = new_desc
        args.group       = new_group
        args.cwd         = new_cwd

    # Apply changes
    if getattr(args, "type", None) and args.type in ALIAS_TYPES:
        atype = args.type
        info["type"] = atype

    if getattr(args, "script", None):
        if atype in ("url", "inline"):
            if atype == "url" and not validate_url(args.script):
                print(_r(f"  Not a valid URL: {args.script}"))
                sys.exit(1)
            info["target"] = args.script
            info.pop("script", None)
        else:
            new_script = Path(args.script).resolve()
            if not new_script.exists():
                print(_r(f"  File not found: {new_script}"))
                sys.exit(1)
            info["script"] = str(new_script)
            info.pop("target", None)

    if getattr(args, "interpreter", None) is not None:
        if atype != "run":
            print(_y(f"  --interpreter is ignored for type '{atype}'"))
        else:
            info["interpreter"] = args.interpreter

    if getattr(args, "description", None) is not None:
        info["description"] = args.description

    if getattr(args, "group", None) is not None:
        g = args.group.strip()
        if g and not validate_group(g):
            print(_r(f"  Invalid group name '{g}'"))
            sys.exit(1)
        if g:
            info["group"] = g
        else:
            info.pop("group", None)

    if getattr(args, "cwd", None) is not None:
        info["cwd"] = args.cwd or ""

    if getattr(args, "env", None):
        info["env"] = {**info.get("env", {}), **parse_env(args.env)}

    # Handle rename
    new_alias = getattr(args, "new_alias", None) or alias
    remove_launcher(alias)
    if new_alias != alias:
        if not validate_alias(new_alias):
            print(_r(f"  Invalid alias name '{new_alias}'"))
            sys.exit(1)
        if new_alias in cfg["aliases"]:
            print(_r(f"  '{new_alias}' already exists."))
            sys.exit(1)
        del cfg["aliases"][alias]

    backup_config()
    cfg["aliases"][new_alias] = info
    save_config(cfg)
    write_launcher(new_alias, info)

    label = f"'{alias}'" + (f" → '{new_alias}'" if new_alias != alias else "")
    print(_g(f"  ✓ Updated {label}"))

    class _LA:
        group = None; json = False; sort = None; check = False
    cmd_list(_LA())


def cmd_rename(args):
    cfg = load_config()
    old = args.old_alias
    new = args.new_alias

    if old not in cfg["aliases"]:
        print(_r(f"  '{old}' not found."))
        sys.exit(1)
    if new in cfg["aliases"]:
        print(_r(f"  '{new}' already exists."))
        sys.exit(1)
    if not validate_alias(new):
        print(_r(f"  '{new}' isn't a valid name."))
        sys.exit(1)

    backup_config()
    entry = cfg["aliases"].pop(old)
    cfg["aliases"][new] = entry
    remove_launcher(old)
    write_launcher(new, entry)
    save_config(cfg)
    print(_g(f"  ✓ Renamed '{old}' → '{new}'"))


def cmd_freeze(args):
    cfg   = load_config()
    alias = args.alias
    if alias not in cfg["aliases"]:
        print(_r(f"  '{alias}' not found."))
        sys.exit(1)
    cfg["aliases"][alias]["locked"] = True
    save_config(cfg)
    print(_g(f"  ✓ '{alias}' is now locked 🔒"))


def cmd_unfreeze(args):
    cfg   = load_config()
    alias = args.alias
    if alias not in cfg["aliases"]:
        print(_r(f"  '{alias}' not found."))
        sys.exit(1)
    cfg["aliases"][alias].pop("locked", None)
    save_config(cfg)
    print(_g(f"  ✓ '{alias}' is unlocked"))


def cmd_run(args):
    cfg      = load_config()
    aliases  = args.aliases
    parallel = getattr(args, "parallel", False)

    for alias in aliases:
        if alias not in cfg["aliases"]:
            print(_r(f"  '{alias}' not found."))
            sys.exit(1)

    def _run_one(alias):
        launcher = BIN_DIR / (f"{alias}.bat" if IS_WINDOWS else alias)
        if not launcher.exists():
            print(_r(f"  Launcher missing for '{alias}'. Try: shalias doctor --fix"))
            return
        subprocess.run([str(launcher)], check=False)

    if parallel and len(aliases) > 1:
        with ThreadPoolExecutor() as ex:
            list(ex.map(_run_one, aliases))
    else:
        for alias in aliases:
            _run_one(alias)


def cmd_run_group(args):
    cfg     = load_config()
    group   = args.group
    members = [a for a, i in cfg.get("aliases", {}).items()
               if i.get("group") == group]
    if not members:
        print(_r(f"  No aliases in group '{group}'."))
        sys.exit(1)
    for alias in sorted(members):
        launcher = BIN_DIR / (f"{alias}.bat" if IS_WINDOWS else alias)
        if launcher.exists():
            subprocess.run([str(launcher)], check=False)


def cmd_stats(args):
    cfg     = load_config()
    aliases = cfg.get("aliases", {})

    if not aliases:
        print("\n  No aliases yet.\n")
        return

    tracked = [(a, i) for a, i in aliases.items() if i.get("use_count", 0) > 0]
    tracked.sort(key=lambda x: x[1].get("use_count", 0), reverse=True)

    print()
    print(_b("  Usage Stats"))
    print("  " + "─" * 55)

    if not tracked:
        print("  Nothing run yet — go use some aliases!")
    else:
        for alias, info in tracked:
            bar  = "█" * min(info["use_count"], 30)
            last = info.get("last_used", "never")[:10]
            print(f"  {alias:<20} {bar:<32} {info['use_count']} runs  (last: {last})")

    print()
    total = sum(i.get("use_count", 0) for i in aliases.values())
    print(f"  Total: {total} runs across {len(aliases)} aliases")
    print()


def cmd_export(args):
    cfg  = load_config()
    path = Path(args.output)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
    print(_g(f"  ✓ Exported to {path}"))


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
    print(_g(f"\n  ✓ Imported {len(aliases)} aliases\n"))


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
        print(_g(f"  ✓ Updated to {remote_ver}"))

    except Exception as e:
        print(_r(f"  Update failed: {e}"))


def cmd_completion(args):
    shell   = args.shell.lower()
    aliases = list(load_config().get("aliases", {}).keys())
    names   = " ".join(aliases)

    if shell == "bash":
        print(f"""# shalias bash completion
# Add to ~/.bashrc:  source <(shalias completion bash)
_shalias_complete() {{
  local cur="${{COMP_WORDS[COMP_CWORD]}}"
  local cmds="add chain clone remove list search run run-group stats doctor edit rename freeze unfreeze export import update completion config uninstall"
  local aliases="{names}"
  if [ "${{COMP_CWORD}}" -eq 1 ]; then
    COMPREPLY=( $(compgen -W "$cmds" -- "$cur") )
  else
    COMPREPLY=( $(compgen -W "$aliases" -- "$cur") )
  fi
}}
complete -F _shalias_complete shalias""")

    elif shell == "zsh":
        print(f"""# shalias zsh completion
# Add to ~/.zshrc:  source <(shalias completion zsh)
_shalias() {{
  local -a cmds aliases
  cmds=(add chain clone remove list search run run-group stats doctor edit rename freeze unfreeze export import update completion config uninstall)
  aliases=({names})
  _arguments '1:command:($cmds)' '2:alias:($aliases)'
}}
compdef _shalias shalias""")

    else:
        print(_r(f"  Unknown shell '{shell}'. Options: bash, zsh"))


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
        print(_g("  ✓ Launchers removed"))
    print()
    print("  Your aliases are still saved at ~/.shalias/config.json")
    print("  Delete it manually if you want a completely clean slate.")
    print()
    print("  Bye! o/")
    print()

# ══════════════════════════════════════════════════════════════════════════════
# Argument parser
# ══════════════════════════════════════════════════════════════════════════════

def build_parser():
    p = argparse.ArgumentParser(
        prog="shalias",
        description="shalias — run your scripts from anywhere",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = p.add_subparsers(dest="command")

    # install
    sub.add_parser("install", help="One-time setup on this machine")

    # add
    a = sub.add_parser("add", help="Register a script, file, URL, or command as an alias")
    a.add_argument("script",                       help="Script/file path, URL, or shell command (with --inline)")
    a.add_argument("--alias",    "-a",             help="Name for the command (default: filename stem)")
    a.add_argument("--type",     "-t",             help="Override auto-detected type: run | open | url")
    a.add_argument("--interpreter", "-i",          help="Override interpreter (e.g. python3, node)")
    a.add_argument("--inline",   action="store_true", help="Treat the first arg as a raw shell command")
    a.add_argument("--cwd",                        help="Working dir: 'script' | 'current' | /absolute/path")
    a.add_argument("--env",      action="append",  metavar="KEY=VAL",
                                                   help="Bake an env var into the launcher (repeatable)")
    a.add_argument("--group",    "-g",             help="Assign to a group")
    a.add_argument("--description", "-d",          help="Short description")

    # chain
    ch = sub.add_parser("chain", help="Create an alias that runs other aliases in sequence")
    ch.add_argument("name",                        help="Name for the chain alias")
    ch.add_argument("--run",     nargs="+", required=True, metavar="ALIAS",
                                                   help="Aliases to run in order")
    ch.add_argument("--group",   "-g",             help="Assign to a group")
    ch.add_argument("--description", "-d",         help="Short description")

    # clone
    cl = sub.add_parser("clone", help="Duplicate an alias under a new name")
    cl.add_argument("source",                      help="Alias to copy")
    cl.add_argument("dest",                        help="New alias name")

    # remove
    rm = sub.add_parser("remove", help="Delete an alias")
    rm.add_argument("alias")

    # list
    ls = sub.add_parser("list", help="Show all aliases")
    ls.add_argument("--group",  "-g",              help="Filter by group")
    ls.add_argument("--sort",   choices=["recent", "uses"],
                                                   help="Sort by most recent or most used")
    ls.add_argument("--check",  action="store_true",
                                                   help="Also verify that file targets still exist")
    ls.add_argument("--json",   action="store_true", help="Output as JSON")

    # search
    sr = sub.add_parser("search", help="Search aliases by keyword")
    sr.add_argument("query")

    # run
    ru = sub.add_parser("run", help="Run one or more aliases by name")
    ru.add_argument("aliases", nargs="+",          help="Alias name(s)")
    ru.add_argument("--parallel", action="store_true", help="Run them all at the same time")

    # run-group
    rg = sub.add_parser("run-group", help="Run every alias in a group")
    rg.add_argument("group")

    # stats
    sub.add_parser("stats", help="Show usage statistics")

    # doctor
    doc = sub.add_parser("doctor", help="Check for broken aliases")
    doc.add_argument("--fix", action="store_true", help="Auto-remove aliases pointing to missing files")

    # edit
    ed = sub.add_parser("edit", help="Modify an alias (interactive if no flags given)")
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

    # rename
    rn = sub.add_parser("rename", help="Rename an alias")
    rn.add_argument("old_alias")
    rn.add_argument("new_alias")

    # freeze / unfreeze
    fr = sub.add_parser("freeze",   help="Lock an alias so it can't be edited or removed")
    fr.add_argument("alias")
    uf = sub.add_parser("unfreeze", help="Unlock a frozen alias")
    uf.add_argument("alias")

    # export / import
    ex = sub.add_parser("export", help="Save all aliases to a JSON file")
    ex.add_argument("output", nargs="?", default="shalias_backup.json")
    im = sub.add_parser("import", help="Load aliases from a JSON file")
    im.add_argument("input")
    im.add_argument("--dry-run", action="store_true", dest="dry_run",
                    help="Preview what would be imported, without applying it")

    # update
    sub.add_parser("update", help="Pull the latest version from GitHub")

    # completion
    co = sub.add_parser("completion", help="Print a shell completion script")
    co.add_argument("shell", choices=["bash", "zsh"])

    # config
    sub.add_parser("config", help="Open config.json in your default editor")

    # uninstall
    sub.add_parser("uninstall", help="Remove shalias from PATH and delete all launchers")

    # internal — hidden from help
    tr = sub.add_parser("_track", help=argparse.SUPPRESS)
    tr.add_argument("alias")

    return p


COMMANDS = {
    "install":    cmd_install,
    "add":        cmd_add,
    "chain":      cmd_chain,
    "clone":      cmd_clone,
    "remove":     cmd_remove,
    "list":       cmd_list,
    "search":     cmd_search,
    "run":        cmd_run,
    "run-group":  cmd_run_group,
    "stats":      cmd_stats,
    "doctor":     cmd_doctor,
    "edit":       cmd_edit,
    "rename":     cmd_rename,
    "freeze":     cmd_freeze,
    "unfreeze":   cmd_unfreeze,
    "export":     cmd_export,
    "import":     cmd_import,
    "update":     cmd_update,
    "completion": cmd_completion,
    "config":     cmd_config,
    "uninstall":  cmd_uninstall,
    "_track":     cmd_track,
}


def main():
    parser = build_parser()
    args   = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    fn = COMMANDS.get(args.command)
    if not fn:
        print(_r(f"  Unknown command: {args.command}"))
        parser.print_help()
        sys.exit(1)

    fn(args)


if __name__ == "__main__":
    main()