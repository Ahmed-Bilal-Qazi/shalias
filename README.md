# Pathman — Windows Script PATH Manager - Version 1.3 

Run scripts, open files, and launch URLs as permanent Command Prompt commands.

Pathman generates `.bat` launchers and safely manages your user PATH so you can execute anything from anywhere.

---

## Table of Contents

* [Quick Start](#quick-start)
* [Installation](#installation)
* [Register Targets](#register-targets)
* [Commands](#commands)
* [Examples](#examples)
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

## Quick Start

### 1. Install (one-time setup)

```cmd
python pathman.py install
```

This will:

* Create `%USERPROFILE%\.pathman\bin\`
* Add it to your user PATH
* Generate `pathman.bat`
* Create `config.json`

> Open a new Command Prompt window after installation.

---

### 2. Add a Command

```cmd
pathman add myscript.py --alias mycmd
```

Run it from anywhere:

```cmd
mycmd
mycmd --help
mycmd input.txt
```

---

## Installation

```cmd
python pathman.py install
```

| Action            | Result                       |
| ----------------- | ---------------------------- |
| Create directory  | `%USERPROFILE%\.pathman\bin` |
| Update PATH       | Adds bin to user PATH        |
| Create launcher   | `pathman.bat`                |
| Initialize config | `config.json`                |

---

## Register Targets

Pathman supports three types:

| Type   | Description                          |
| ------ | ------------------------------------ |
| `run`  | Execute scripts using an interpreter |
| `open` | Open files with default application  |
| `url`  | Open links in browser                |

---

## Commands

| Command             | Description                   |
| ------------------- | ----------------------------- |
| `pathman install`   | Initial setup                 |
| `pathman add`       | Register script, file, or URL |
| `pathman list`      | Show all aliases              |
| `pathman remove`    | Delete alias                  |
| `pathman edit`      | Modify alias                  |
| `pathman export`    | Export aliases                |
| `pathman import`    | Import aliases                |
| `pathman config`    | Open config file              |
| `pathman uninstall` | Remove tool                   |

---

## Examples

```cmd
# Run script
pathman add app.py --alias app

# Run with interpreter
pathman add build.js --alias build --interpreter node

# Open file
pathman add report.pdf --alias report --type open

# Open URL
pathman add https://github.com --alias gh --type url

# Add description
pathman add script.py --alias run --description "Main script"

# Edit alias
pathman edit run --script newscript.py

# Rename alias
pathman edit run --new-alias run2

# Remove alias
pathman remove run
```

---

## How It Works

```
pathman add script.py --alias run
        │
        ▼
Creates: %USERPROFILE%\.pathman\bin\run.bat
        │
        └── python "C:\full\path\script.py" %*

PATH includes .pathman\bin
        │
        ▼
You can run: run [args]
```

Each alias is a `.bat` file that forwards all arguments.

---

## Supported Interpreters

| Extension | Interpreter |
| --------- | ----------- |
| `.py`     | python      |
| `.js`     | node        |
| `.rb`     | ruby        |
| `.pl`     | perl        |
| `.sh`     | bash        |
| `.ps1`    | powershell  |
| other     | python      |

Override using `--interpreter`.

---

## Configuration

Location:

```
%USERPROFILE%\.pathman\config.json
```

Open:

```cmd
pathman config
```

Example:

```json
{
  "aliases": {
    "app": {
      "type": "run",
      "script": "C:\\scripts\\app.py",
      "interpreter": "python",
      "description": "Main app"
    }
  }
}
```

---

## Backup and Restore

### Export

```cmd
pathman export backup.json
```

### Import

```cmd
pathman import backup.json
```

Overwrite existing:

```cmd
pathman import backup.json --overwrite
```

---

## Uninstall

```cmd
pathman uninstall
```

| Action            | Result                   |
| ----------------- | ------------------------ |
| Remove PATH entry | `.pathman\bin` removed   |
| Delete launchers  | All `.bat` files removed |
| Keep config       | `config.json` preserved  |

---

## Troubleshooting

### Command not recognized

* Restart Command Prompt
* Ensure `.pathman\bin` is in PATH

---

### Script not running

* Interpreter missing
* Wrong interpreter

Fix:

```cmd
pathman edit mycmd --interpreter python
```

---

### Alias shows MISSING

* File moved or deleted

Fix:

```cmd
pathman edit mycmd --script newpath
```

---

## Requirements

* Windows 10 or 11
* Python 3.8+
* No administrator privileges required

---

## File Structure

```
%USERPROFILE%\.pathman/
├── bin/           # .bat launchers
├── config.json    # alias registry
```

---

## Contributing

* Report issues for bugs or improvements
* Submit pull requests
* Keep the tool simple and maintainable

---
