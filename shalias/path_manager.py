"""
Manages adding / removing ~/.shalias/bin from the user's PATH.

On Windows this goes via the registry (HKCU\\Environment).
On Unix it patches the relevant shell rc files.
"""
import subprocess

from .constants import BIN_DIR, HOME, IS_WINDOWS
from .colors import _g, _r, _y


# ── Public API ────────────────────────────────────────────────────────────────

def add_to_path() -> None:
    if IS_WINDOWS:
        _win_add(str(BIN_DIR))
    else:
        _unix_add()


def remove_from_path() -> None:
    if IS_WINDOWS:
        _win_remove(str(BIN_DIR))
    else:
        _unix_remove()


def shell_configs() -> list:
    """Return existing shell rc files (Unix only)."""
    candidates = [
        ".bashrc", ".zshrc", ".profile", ".bash_profile",
        ".config/fish/config.fish",
    ]
    return [HOME / f for f in candidates if (HOME / f).exists()]


# ── Windows ───────────────────────────────────────────────────────────────────

def _win_get_path() -> list:
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


def _win_set_path(entries: list) -> None:
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
        import sys; sys.exit(1)
    # Broadcast the change so new shells pick it up without a reboot
    subprocess.run(["setx", "_SHALIAS_REFRESH", "1"], capture_output=True)
    subprocess.run(
        ["reg", "delete", "HKCU\\Environment", "/v", "_SHALIAS_REFRESH", "/f"],
        capture_output=True,
    )


def _win_add(entry: str) -> None:
    entries = _win_get_path()
    if entry.lower() not in [e.lower() for e in entries]:
        entries.append(entry)
        _win_set_path(entries)
        print(_g(f"  Added to PATH: {entry}"))
    else:
        print(_g(f"  Already in PATH: {entry}"))


def _win_remove(entry: str) -> None:
    entries = _win_get_path()
    cleaned = [e for e in entries if e.lower() != entry.lower()]
    if len(cleaned) < len(entries):
        _win_set_path(cleaned)
        print(_g(f"  Removed from PATH: {entry}"))


# ── Unix ──────────────────────────────────────────────────────────────────────

def _unix_add() -> None:
    line   = f'export PATH="{BIN_DIR}:$PATH"  # shalias'
    marker = str(BIN_DIR)
    configs = shell_configs() or [HOME / ".bashrc"]
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


def _unix_remove() -> None:
    marker = str(BIN_DIR)
    for rc in shell_configs():
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
