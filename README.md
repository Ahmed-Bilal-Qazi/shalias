
---

# shalias — Cross-Platform Script Alias Manager · v2.0

> Run scripts, open files, and launch URLs as permanent terminal commands — on **Windows, macOS, and Linux**.

`shalias` creates native launchers (`.bat` on Windows, shell scripts on Unix) and manages your PATH so you can execute anything from anywhere with minimal friction.

---

## Table of Contents

* [What's New in v2.0](#whats-new-in-v20)
* [Quick Start](#quick-start)
* [Installation](#installation)
* [Register Targets](#register-targets)
* [Commands](#commands)
* [Examples](#examples)
* [Groups](#groups)
* [Search](#search)
* [Execution](#execution)
* [Stats](#stats)
* [Doctor](#doctor)
* [Locking](#locking)
* [Autocompletion](#autocompletion)
* [Auto Update](#auto-update)
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

## What's New in v2.0

| Feature            | Description                                         |
| ------------------ | --------------------------------------------------- |
| Parallel execution | Run multiple aliases concurrently with `--parallel` |
| Group execution    | Execute all aliases in a group with `run-group`     |
| Usage tracking     | Track run count and last used timestamps            |
| Stats dashboard    | View alias usage insights via `shalias stats`       |
| Alias locking      | Prevent edits/removal with `freeze` / `unfreeze`    |
| JSON output        | Machine-readable output for scripting (`--json`)    |
| Import preview     | `--dry-run` mode before importing                   |
| Auto update        | Background version check + manual update command    |
| Autocompletion     | Bash and Zsh completion support                     |
| Improved doctor    | Better diagnostics and optional auto-fix            |
| Safer config       | Atomic writes + rolling backups                     |

---

## Quick Start

### 1. Install

```bash
python shalias.py install
```

Open a **new terminal window**.

### 2. Add a Command

```bash
shalias add myscript.py --alias mycmd
```

### 3. Run It

```bash
mycmd
mycmd --help
```

---

## Installation

```bash
python shalias.py install
```

| Action            | Result                     |
| ----------------- | -------------------------- |
| Create directory  | `~/.shalias/bin/`          |
| Update PATH       | Adds `bin/` to PATH        |
| Create launcher   | `shalias` or `shalias.bat` |
| Initialize config | `~/.shalias/config.json`   |

---

## Register Targets

| Type   | Description                |
| ------ | -------------------------- |
| `run`  | Execute a script (default) |
| `open` | Open a file                |
| `url`  | Open a URL                 |

---

## Commands

| Command              | Description                |
| -------------------- | -------------------------- |
| `shalias install`    | Setup environment          |
| `shalias add`        | Register alias             |
| `shalias list`       | List aliases               |
| `shalias search`     | Search aliases             |
| `shalias run`        | Run one or more aliases    |
| `shalias run-group`  | Run all aliases in a group |
| `shalias stats`      | Show usage statistics      |
| `shalias doctor`     | Diagnose issues            |
| `shalias edit`       | Modify alias               |
| `shalias rename`     | Rename alias               |
| `shalias remove`     | Delete alias               |
| `shalias freeze`     | Lock alias                 |
| `shalias unfreeze`   | Unlock alias               |
| `shalias export`     | Export config              |
| `shalias import`     | Import config              |
| `shalias update`     | Check for updates          |
| `shalias completion` | Generate shell completion  |
| `shalias config`     | Open config                |
| `shalias uninstall`  | Remove from system         |

---

## Examples

```bash
# Scripts
shalias add app.py --alias app
shalias add build.js --alias build --interpreter node

# Files
shalias add report.pdf --alias report --type open

# URLs
shalias add https://github.com --alias gh --type url

# Groups
shalias add deploy.py --alias deploy --group devops

# Editing
shalias edit app --script new.py
shalias rename app myapp

# Locking
shalias freeze deploy
shalias unfreeze deploy
```

---

## Groups

```bash
shalias add test.py --alias test --group dev
shalias list --group dev
shalias run-group dev
```

---

## Search

```bash
shalias search python
shalias search devops
```

Searches across names, descriptions, groups, and targets.

---

## Execution

### Run single

```bash
shalias run app
```

### Run multiple

```bash
shalias run app test build
```

### Parallel

```bash
shalias run app test --parallel
```

---

## Stats

```bash
shalias stats
```

Displays:

* run counts
* last used timestamps
* activity summary

---

## Doctor

```bash
shalias doctor
```

Checks:

* missing files
* missing interpreters
* broken launchers

Auto-fix:

```bash
shalias doctor --fix
```

---

## Locking

```bash
shalias freeze myalias
shalias unfreeze myalias
```

Prevents accidental modification or deletion.

---

## Autocompletion

### Bash

```bash
source <(shalias completion bash)
```

### Zsh

```bash
source <(shalias completion zsh)
```

---

## Auto Update

```bash
shalias update
```

Checks for new versions and upgrades.

---

## How It Works

```
shalias add script.py --alias run
        ↓
Creates launcher in ~/.shalias/bin/
        ↓
Adds directory to PATH
        ↓
You run: run [args]
```

Each alias forwards arguments directly to the target.

---

## Supported Interpreters

| Extension | Interpreter      |
| --------- | ---------------- |
| `.py`     | python3 / python |
| `.js`     | node             |
| `.ts`     | ts-node          |
| `.sh`     | bash             |
| `.ps1`    | powershell       |
| `.rb`     | ruby             |
| `.pl`     | perl             |
| `.lua`    | lua              |
| `.php`    | php              |
| `.r`      | Rscript          |
| `.go`     | go run           |

Override manually:

```bash
shalias add script.xyz --alias test --interpreter custom_cmd
```

---

## Configuration

```
~/.shalias/config.json
```

Open:

```bash
shalias config
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

Preview:

```bash
shalias import backup.json --dry-run
```

---

## Uninstall

```bash
shalias uninstall
```

Removes:

* PATH entry
* launchers

Keeps:

* config file

---

## Troubleshooting

### Command not found

* Restart terminal
* Verify PATH includes `~/.shalias/bin`

### Script fails

* Fix interpreter:

```bash
shalias edit mycmd --interpreter python3
```

### Broken alias

```bash
shalias doctor
```

---

## Requirements

* Python 3.8+
* Windows, macOS, or Linux
* No admin privileges required

---

## File Structure

```
~/.shalias/
├── bin/
├── config.json
└── backups/
```

---

## Contributing

* Open issues for bugs or ideas
* Keep it lightweight and dependency-free
* Include `shalias doctor` output when reporting issues

---

**shalias v2.0**
