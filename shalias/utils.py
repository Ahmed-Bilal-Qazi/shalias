"""
Shared helpers: validation, type/interpreter detection, background
update check, output formatting, and --format flag support.
"""
import json
import re
import sys
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from .colors import _b, _d, _g, _r, _y
from .constants import (
    ALIAS_TYPES,
    BIN_DIR,
    INTERPRETER_MAP,
    IS_WINDOWS,
    OPEN_EXTENSIONS,
    UPDATE_URL,
    VERSION,
)


# ── Validators ────────────────────────────────────────────────────────────────

_SAFE_NAME = re.compile(r"^[A-Za-z0-9_-]+$")


def now_stamp() -> str:
    """UTC timestamp we record on new aliases, so `list --sort recent` works."""
    return datetime.now(timezone.utc).isoformat()


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
            print(_y(f"  Skipping malformed --env value '{item}' - expected KEY=VALUE"))
            continue
        k, _, v = item.partition("=")
        result[k.strip()] = v.strip()
    return result


def check_alias_free(alias: str, cfg: dict) -> None:
    """Exit with a helpful message if *alias* is invalid or already taken."""
    if not validate_alias(alias):
        print(_r(f"  '{alias}' isn't a valid name."))
        print("  Use only letters, numbers, hyphens (-), and underscores (_).")
        sys.exit(1)
    if alias in cfg["aliases"]:
        print(_r(f"  '{alias}' already exists."))
        print(f"  To change it: shalias edit {alias}")
        sys.exit(1)


# ── Type / interpreter detection ──────────────────────────────────────────────

def detect_type(target: str) -> str:
    if target.startswith("http://") or target.startswith("https://"):
        return "url"
    suffix = Path(target).suffix.lower()
    if suffix in INTERPRETER_MAP:
        return "run"
    if suffix in OPEN_EXTENSIONS:
        return "open"
    return "run"


def detect_interpreter(script_path: Path) -> str:
    return INTERPRETER_MAP.get(
        script_path.suffix.lower(),
        "python3" if not IS_WINDOWS else "python",
    )


# ── Background update check ───────────────────────────────────────────────────

def check_update_async(cfg: dict) -> None:
    """Fire a version check in the background - never blocks the CLI."""
    meta = cfg.setdefault("meta", {})
    if time.time() - meta.get("last_update_check", 0) < 86400:
        return

    def _do() -> None:
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
            from .config import save_config
            save_config(cfg)
        except Exception:
            pass

    threading.Thread(target=_do, daemon=True).start()


# ── Output formatting ─────────────────────────────────────────────────────────

def print_alias_summary(alias: str, entry: dict, launcher: Path) -> None:
    atype = entry.get("type", "run")
    print()
    print(_g(f"  + {alias}"))
    print(f"    type        : {atype}")
    if atype == "chain":
        print(f"    runs        : {' -> '.join(entry.get('chain', []))}")
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


# ── --format helpers ──────────────────────────────────────────────────────────

VALID_FORMATS = ("table", "json", "plain")


def resolve_format(args) -> str:
    """
    Normalize the --format flag value. Falls back to 'table' if not set.
    Keeps backward compat with the legacy --json flag.
    """
    fmt = getattr(args, "format", None)
    if fmt:
        return fmt.lower()
    # Legacy flag support
    if getattr(args, "json", False):
        return "json"
    return "table"


def format_aliases(aliases: dict, fmt: str, cmd_name: str = "shalias") -> None:
    """Render *aliases* according to *fmt* (table | json | plain)."""
    if fmt == "json":
        print(json.dumps(aliases, indent=2))
        return

    if fmt == "plain":
        for alias, info in aliases.items():
            atype  = info.get("type", "run")
            target = (
                info.get("target", "") if atype in ("url", "inline")
                else " -> ".join(info.get("chain", [])) if atype == "chain"
                else info.get("script", "")
            )
            print(f"{alias}\t{atype}\t{target}")
        return

    # ── table (default) ───────────────────────────────────────────────────────
    from .colors import _cy
    header  = f"  {'ALIAS':<20} {'TYPE':<8} {'STATUS':<8} {'GROUP':<14} DESCRIPTION / TARGET"
    divider = "  " + "-" * 89

    def _row(alias: str, info: dict) -> None:
        atype  = info.get("type", "run")
        desc   = info.get("description", "") or ""
        grp    = info.get("group", "")
        lock   = " [locked]" if info.get("locked") else ""
        target = (
            info.get("target", "") if atype in ("url", "inline")
            else " -> ".join(info.get("chain", [])) if atype == "chain"
            else info.get("script", "")
        )
        ok       = atype in ("url", "inline", "chain") or Path(target).exists()
        status   = _g("ok") if ok else _r("missing")
        label    = desc[:30] if desc else _d(target[:40])
        raw_stat = "ok" if ok else "missing"
        pad      = " " * max(0, 8 - len(raw_stat))
        print(f"  {alias + lock:<20} {atype:<8} {status}{pad} {grp:<14} {label}")

    grouped   = {}
    ungrouped = {}
    for alias, info in aliases.items():
        g = info.get("group", "")
        (grouped.setdefault(g, {}) if g else ungrouped)[alias] = info

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
        f"  *  {cmd_name} search <term>"
        f"  *  {cmd_name} list --check"
        f"  *  {cmd_name} doctor"
    ))
    print()
