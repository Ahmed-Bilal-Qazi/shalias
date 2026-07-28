"""
shalias export, import, update, uninstall
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

from ..colors import _g, _r, _y
from ..config import backup_config, load_config, save_config
from ..constants import BIN_DIR, CONFIG_FILE
from ..launcher import write_launcher
from ..path_manager import remove_from_path


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

    print(f"\n  {'DRY RUN - ' if dry_run else ''}Importing {len(aliases)} alias(es):\n")
    for alias, info in aliases.items():
        print(f"    {alias:<20} {info.get('type', 'run'):<8} "
              f"{info.get('script', info.get('target', ''))}")

    if dry_run:
        print("\n  (dry run - nothing was changed)\n")
        return

    cfg = load_config()
    backup_config()
    for alias, info in aliases.items():
        cfg["aliases"][alias] = info
        write_launcher(alias, info)
    save_config(cfg)
    print(_g(f"\n  + Imported {len(aliases)} aliases\n"))


def install_mode() -> str:
    """
    How this copy of shalias got onto the machine: 'source', 'pipx' or 'pip'.

    A checkout has pyproject.toml two levels above this file; pipx keeps every
    app in its own venv under a directory literally named 'pipx'.
    """
    root = Path(__file__).resolve().parents[2]
    if (root / "pyproject.toml").exists() or (root / ".git").exists():
        return "source"
    if "pipx" in Path(sys.prefix).parts:
        return "pipx"
    return "pip"


def cmd_update(args):
    mode = install_mode()

    if mode == "source":
        print(_y("\n  This is a source checkout, so shalias won't overwrite it."))
        print(f"  Pull it yourself:  cd {Path(__file__).resolve().parents[2]} && git pull\n")
        return

    if mode == "pipx":
        cmd = ["pipx", "upgrade", "shalias"]
    else:
        cmd = [sys.executable, "-m", "pip", "install", "--upgrade", "shalias"]
    printable = " ".join(cmd)

    print(f"\n  Running: {printable}\n")
    try:
        code = subprocess.run(cmd).returncode
    except OSError as e:
        print(_r(f"\n  Couldn't run {cmd[0]}: {e}"))
        print(f"  Do it by hand:  {printable}\n")
        sys.exit(1)

    if code != 0:
        print(_r(f"\n  Update failed (exit {code})."))
        print(f"  Try it by hand:  {printable}\n")
        sys.exit(1)

    print(_g("\n  + Done. Check it with: shalias --version\n"))


def cmd_uninstall(args):
    print("\n  Removing shalias from PATH...")
    remove_from_path()
    if BIN_DIR.exists():
        shutil.rmtree(BIN_DIR)
        print(_g("  + Launchers removed"))
    print()
    print(f"  Your aliases are still saved at {CONFIG_FILE}")
    print("  Delete it manually if you want a completely clean slate.")
    print()
    print("  Bye! o/")
    print()


