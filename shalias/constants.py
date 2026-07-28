"""
Central place for version info, paths, platform flags, and lookup tables.
Everything else imports from here - nothing imports back into this file.
"""
import platform
from pathlib import Path

# ── Version ───────────────────────────────────────────────────────────────────
VERSION = "4.0.0"

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

# ── Alias types ───────────────────────────────────────────────────────────────
ALIAS_TYPES = ("run", "open", "url", "inline", "chain")

# ── Interpreter lookup (extension -> default command) ─────────────────────────
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

# Extensions that should be opened with the OS default viewer, not executed
OPEN_EXTENSIONS = frozenset({
    ".pdf", ".docx", ".doc", ".xlsx", ".xls", ".pptx", ".ppt",
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".mp4", ".mp3",
    ".zip", ".tar", ".gz", ".csv",
})

BANNER = r"""
 _____ _           _ _
/ ____| |         | (_)
| (___ | |__   __ _| |_  __ _ ___
 \___ \| '_ \ / _` | | |/ _` / __|
 ____) | | | | (_| | | | (_| \__ \
|_____/|_| |_|\__,_|_|_|\__,_|___/
 Cross-Platform Script Alias Manager  v{version}
""".format(version=VERSION)
