"""
Config load / save / backup.
The config file is a single JSON object:
  {
    "aliases": { "<name>": { ... } },
    "groups":  {},
    "meta":    { "command_name": "shalias", ... }
  }

Saves are atomic (write to temp, rename) so a crash mid-write
never leaves a partial file.
"""
import json
import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path

from .constants import BACKUP_DIR, CONFIG_FILE, SHALIAS_DIR
from .colors import _y


# ── Load ──────────────────────────────────────────────────────────────────────

def load_config() -> dict:
    """Return the config dict, always with the three top-level keys present."""
    if not CONFIG_FILE.exists():
        return _blank()
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        data.setdefault("aliases", {})
        data.setdefault("groups",  {})
        data.setdefault("meta",    {})
        return data
    except (json.JSONDecodeError, IOError):
        print(_y("  config.json looks corrupted - starting fresh."))
        print(_y("  Your backups are in ~/.shalias/backups/ if you need them."))
        return _blank()


def _blank() -> dict:
    return {"aliases": {}, "groups": {}, "meta": {}}


# ── Save ──────────────────────────────────────────────────────────────────────

def save_config(cfg: dict) -> None:
    """Atomically write cfg to disk."""
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


# ── Backup ────────────────────────────────────────────────────────────────────

def backup_config() -> None:
    """Copy the current config into the backup directory (keep last 10)."""
    if not CONFIG_FILE.exists():
        return
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    ts  = datetime.now().strftime("%Y%m%d_%H%M%S")
    dst = BACKUP_DIR / f"config_{ts}.json"
    shutil.copy2(CONFIG_FILE, dst)
    # Quietly prune backups older than the 10 most recent
    for old in sorted(BACKUP_DIR.glob("config_*.json"), reverse=True)[10:]:
        try:
            old.unlink()
        except OSError:
            pass


# ── Meta helpers ──────────────────────────────────────────────────────────────

def get_command_name(cfg: dict) -> str:
    """Return the user-chosen command name, defaulting to 'shalias'."""
    return cfg.get("meta", {}).get("command_name", "shalias")
