import platform
import sys
from pathlib import Path

from ..colors import _g
from ..config import CONFIG_FILE, save_config
from ..constants import BACKUP_DIR, BIN_DIR, BANNER, PLATFORM, SHALIAS_DIR, IS_WINDOWS
from ..launcher import write_launcher
from ..path_manager import shell_configs, add_to_path
from ..utils import now_stamp


def cmd_install(args):
    print(BANNER)
    print(f"  Platform : {PLATFORM} ({platform.release()})")
    print(f"  Home     : {Path.home()}")
    print(f"  Install  : {SHALIAS_DIR}")
    print()

    SHALIAS_DIR.mkdir(parents=True, exist_ok=True)
    BIN_DIR.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    # When run as `python shalias/cli.py install` (not pip), create a launcher
    self_path = Path(sys.argv[0]).resolve()
    if self_path.suffix.lower() == ".py" and self_path.exists():
        interp = "python" if IS_WINDOWS else "python3"
        entry  = {
            "type": "run", "script": str(self_path), "interpreter": interp,
            "description": "shalias itself", "added": now_stamp(), "env": {}, "cwd": "",
        }
        launcher = write_launcher("shalias", entry)
        print(_g(f"  Launcher : {launcher}"))
        print(_g(f"  Points to: {self_path}"))
        add_to_path()
    else:
        print(_g("  Installed via pip — shalias is already on your PATH."))

    if not CONFIG_FILE.exists():
        save_config({"aliases": {}, "groups": {}, "meta": {}})

    print(_g(f"  Config   : {CONFIG_FILE}"))
    print()
    if IS_WINDOWS:
        print("  All set! Open a new cmd window and try: shalias list")
    else:
        print("  All set! Reload your shell, then try: shalias list")
        for rc in shell_configs():
            print(f"    source {rc}")
    print()
