"""
Creates and removes the tiny shell-script (or .bat) launchers that
live in ~/.shalias/bin/ and make aliases work from anywhere.

Each launcher does two things in order:
  1. Set any baked-in env vars
  2. cd to the requested working directory, then exec the target
"""
from pathlib import Path

from .constants import BIN_DIR, IS_WINDOWS, IS_LINUX


# ── Public API ────────────────────────────────────────────────────────────────

def write_launcher(alias: str, entry: dict) -> Path:
    """Generate a launcher for *alias* and return its path."""
    BIN_DIR.mkdir(parents=True, exist_ok=True)
    if IS_WINDOWS:
        return _write_bat(alias, entry)
    return _write_sh(alias, entry)


def remove_launcher(alias: str) -> None:
    """Delete the launcher file(s) for *alias* (both .bat and bare)."""
    for name in [alias, f"{alias}.bat",
                 f"{alias}.disabled", f"{alias}.bat.disabled"]:
        p = BIN_DIR / name
        if p.exists():
            p.unlink()


# ── Windows (.bat) ────────────────────────────────────────────────────────────

def _write_bat(alias: str, entry: dict) -> Path:
    path       = BIN_DIR / f"{alias}.bat"
    atype      = entry.get("type", "run")
    target     = entry.get("target") or entry.get("script", "")
    interp     = entry.get("interpreter", "")
    env        = entry.get("env", {})
    cwd        = entry.get("cwd", "")
    chain_list = entry.get("chain", [])

    env_b = _env_win(env)

    if atype == "run":
        cwd_b = _cwd_win(cwd, target)
        body  = f'"{interp}" "{target}" %*\n'
    elif atype == "inline":
        cwd_b = _cwd_win(cwd, "") if cwd not in ("", "current", "script") else ""
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

    path.write_text(f"@echo off\n{env_b}{cwd_b}{body}", encoding="utf-8")
    return path


# ── Unix (bash) ───────────────────────────────────────────────────────────────

def _write_sh(alias: str, entry: dict) -> Path:
    path       = BIN_DIR / alias
    atype      = entry.get("type", "run")
    target     = entry.get("target") or entry.get("script", "")
    interp     = entry.get("interpreter", "")
    env        = entry.get("env", {})
    cwd        = entry.get("cwd", "")
    chain_list = entry.get("chain", [])

    opener = "xdg-open" if IS_LINUX else "open"
    env_b  = _env_unix(env)

    if atype == "run":
        cwd_b = _cwd_unix(cwd, target)
        body  = f'"{interp}" "{target}" "$@"\n'
    elif atype == "inline":
        cwd_b = _cwd_unix(cwd, "") if cwd not in ("", "current", "script") else ""
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

    path.write_text(f"#!/usr/bin/env bash\n{env_b}{cwd_b}{body}", encoding="utf-8")
    path.chmod(0o755)
    return path


# ── Helpers ───────────────────────────────────────────────────────────────────

def _env_unix(env: dict) -> str:
    return "".join(f'export {k}="{v}"\n' for k, v in env.items())


def _env_win(env: dict) -> str:
    return "".join(f"set {k}={v}\n" for k, v in env.items())


def _cwd_unix(cwd: str, script_path: str) -> str:
    if not cwd or cwd == "current":
        return ""
    if cwd == "script":
        return f'cd "{Path(script_path).parent}"\n' if script_path else ""
    return f'cd "{cwd}"\n'


def _cwd_win(cwd: str, script_path: str) -> str:
    if not cwd or cwd == "current":
        return ""
    if cwd == "script":
        return f'cd /d "{Path(script_path).parent}"\n' if script_path else ""
    return f'cd /d "{cwd}"\n'
