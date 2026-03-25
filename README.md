# shalias — Cross-Platform Script Alias Manager · v1.5

> Run scripts, open files, and launch URLs as permanent terminal commands — on **Windows, macOS, and Linux**.

`shalias` generates native launchers (`.bat` on Windows, shell scripts on Unix) and safely manages your shell PATH so you can execute anything from anywhere, with zero friction.

---

## Table of Contents

* [What's New in v1.5](#whats-new-in-v15)
* [Quick Start](#quick-start)
* [Installation](#installation)
* [Register Targets](#register-targets)
* [Commands](#commands)
* [Examples](#examples)
* [Groups](#groups)
* [Search](#search)
* [Doctor](#doctor)
* [How It Works](#how-it-works)
* [Supported Interpreters](#supported-interpreters)
* [Configuration](#configuration)
* [Backup and Restore](#backup-and-restore)
* [Uninstall](#uninstall)
* [Troubleshooting](#troubleshooting)
* [Requirements](#requirements)
* [File Structure](#file-structure)
* [Contributing](#contributing)

---

## What's New in v1.5

| Feature | Description |
|---|---|
|  Cross-platform | Full support for **Linux** and **macOS** alongside Windows |
|  Groups | Organize aliases into named groups (`--group devops`) |
|  Search | Find aliases instantly with `shalias search <term>` |
|  Doctor | Audit all aliases for broken files and missing interpreters |
|  Atomic saves | Config writes are crash-safe (write-then-rename) |
|  More interpreters | Added `ts-node`, `lua`, `php`, `Rscript`, `go run` |
|  Cleaner output | Grouped list view, better error messages, richer summaries |

---

## Quick Start

### 1. Install (one-time setup)

```bash
python shalias.py install
```

Open a **new terminal window** after installation.

### 2. Add a Command

```bash
shalias add myscript.py --alias mycmd
```

### 3. Run It from Anywhere

```bash
mycmd
mycmd --help
mycmd input.txt
```

---

## Installation

```bash
python shalias.py install
```

| Action | Result |
|---|---|
| Create directory | `~/.shalias/bin/` |
| Update PATH | Adds `bin/` to your user PATH |
| Create launcher | `shalias` (or `shalias.bat` on Windows) |
| Initialize config | `~/.shalias/config.json` |

**Windows:** Open a new `cmd` window after installing.  
**Linux / macOS:** Run `source ~/.bashrc` (or `~/.zshrc`), then open a new terminal.

---

## Register Targets

shalias supports three alias types:

| Type | Description |
|---|---|
| `run` | Execute a script using an interpreter (default) |
| `open` | Open a file with its default application |
| `url` | Open a URL in the default browser |

---

## Commands

| Command | Description |
|---|---|
| `shalias install` | One-time setup |
| `shalias add` | Register a script, file, or URL |
| `shalias list` | Show all aliases (optionally filter by group) |
| `shalias search` | Search aliases by name, description, target, or group |
| `shalias doctor` | Audit aliases for broken files and interpreters |
| `shalias remove` | Delete an alias |
| `shalias edit` | Modify an alias |
| `shalias export` | Export aliases to JSON |
| `shalias import` | Import aliases from JSON |
| `shalias config` | Open config file in your default editor |
| `shalias uninstall` | Remove shalias from PATH |

---

## Examples

```bash
# Run scripts
shalias add app.py --alias app
shalias add build.js --alias build --interpreter node
shalias add "C:\my scripts\run.ps1" --alias run

# Open files with their default application
shalias add report.pdf --alias report --type open
shalias add notes.docx --alias notes --type open

# Open URLs in the browser
shalias add https://github.com --alias gh --type url
shalias add https://docs.python.org --alias pydocs --type url

# Add descriptions and groups
shalias add deploy.py --alias deploy --description "Deploy to prod" --group devops
shalias add budget.xlsx --alias budget --type open --group finance

# Edit aliases
shalias edit app --new-alias myapp
shalias edit app --script /new/path/app.py
shalias edit app --group backend
shalias edit app --group ""        # remove from group

# Remove an alias
shalias remove app
```

---

## Groups

Groups let you organize aliases into named categories. Use `--group` when adding or editing.

```bash
# Add with a group
shalias add deploy.sh --alias deploy --group devops
shalias add logs.py --alias logs --group devops
shalias add budget.xlsx --alias budget --type open --group finance

# Filter the list to a specific group
shalias list --group devops

# Move an alias to a different group
shalias edit deploy --group backend

# Remove from group entirely
shalias edit deploy --group ""
```

Groups are displayed as labeled sections in `shalias list`.

---

## Search

Search across alias names, descriptions, targets, groups, and interpreters:

```bash
shalias search python
shalias search devops
shalias search github
shalias search report
```

---

## Doctor

Run a full health check on all your aliases:

```bash
shalias doctor
```

Doctor checks for:

- **MISSING** — target file has been moved or deleted
- **NO LAUNCHER** — the `.bat` or shell script is gone (re-add the alias to fix)
- **NO INTERP** — the interpreter isn't found in PATH
- **NO TARGET** — no script path stored in config
- **OK** — everything is healthy

Fix issues with:

```bash
shalias edit <alias> --script /new/path/to/script.py
shalias edit <alias> --interpreter python3
```

---

## How It Works

```
shalias add script.py --alias run --group devops
        │
        ▼
Creates: ~/.shalias/bin/run        (Unix shell script)
      or %USERPROFILE%\.shalias\bin\run.bat   (Windows)
        │
        └── python3 "/full/path/to/script.py" "$@"

PATH includes ~/.shalias/bin
        │
        ▼
You can run:  run [args]
```

Each alias is a native launcher that forwards all arguments to the target.

---

## Supported Interpreters

| Extension | Default Interpreter |
|---|---|
| `.py` | `python3` (Unix) / `python` (Windows) |
| `.js` | `node` |
| `.ts` | `ts-node` |
| `.rb` | `ruby` |
| `.pl` | `perl` |
| `.sh` | `bash` |
| `.ps1` | `powershell` |
| `.lua` | `lua` |
| `.php` | `php` |
| `.r` / `.R` | `Rscript` |
| `.go` | `go run` |
| other | `python3` / `python` |

Override with `--interpreter`:

```bash
shalias add app.py --alias app --interpreter /path/to/venv/bin/python
```

---

## Configuration

**Location:**

```
~/.shalias/config.json          (Linux / macOS)
%USERPROFILE%\.shalias\config.json   (Windows)
```

**Open in editor:**

```bash
shalias config
```

**Example:**

```json
{
  "aliases": {
    "deploy": {
      "type": "run",
      "script": "/home/user/scripts/deploy.py",
      "interpreter": "python3",
      "description": "Deploy to production",
      "group": "devops"
    },
    "gh": {
      "type": "url",
      "target": "https://github.com",
      "description": "GitHub",
      "group": "docs"
    }
  }
}
```

---

## Backup and Restore

### Export

```bash
shalias export backup.json
```

### Import

```bash
shalias import backup.json
```

### Import (overwrite existing)

```bash
shalias import backup.json --overwrite
```

Backups are plain JSON — easy to version-control or share across machines.

---

## Uninstall

```bash
shalias uninstall
```

| Action | Result |
|---|---|
| Remove PATH entry | `~/.shalias/bin` removed from PATH |
| Delete launchers | All launcher files deleted |
| Keep config | `config.json` is preserved |

---

## Troubleshooting

### Command not recognized

- Open a new terminal window
- Confirm `~/.shalias/bin` is in `$PATH` (`echo $PATH`)
- On Linux/macOS, run `source ~/.bashrc` or `source ~/.zshrc`

### Script not running

- Interpreter may be missing or named differently
- Fix with: `shalias edit mycmd --interpreter python3`
- Check all issues with: `shalias doctor`

### Alias shows MISSING

- The target file was moved or deleted
- Fix with: `shalias edit mycmd --script /new/path/script.py`

---

## Requirements

- Python 3.8+
- Windows 10/11, macOS 11+, or any modern Linux distro
- No administrator / root privileges required

---

## File Structure

```
~/.shalias/
├── bin/           # Native launchers (.bat on Windows, shell scripts on Unix)
└── config.json    # Alias registry
```

---

## Contributing

- Report bugs or suggest features via GitHub Issues
- Submit pull requests — keep the tool simple and dependency-free
- Run `shalias doctor` before submitting a bug report to include health info

---

*shalias v1.5 — formerly pathman*
