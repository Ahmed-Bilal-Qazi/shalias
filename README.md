# Pathman — Windows Script PATH Manager

Run any script (`.py`, `.js`, `.rb`, `.ps1`, etc.) as a permanent CMD command — no extension needed.

Pathman generates `.bat` launchers and manages your user PATH safely so you can execute scripts from anywhere.

---

## Table of Contents

* [Quick Start](#quick-start)
* [Installation](#installation)
* [Register a Script](#register-a-script)
* [Commands](#commands)
* [Examples](#examples)
* [How It Works](#how-it-works)
* [Supported Interpreters](#supported-interpreters)
* [Configuration](#configuration)
* [Uninstall](#uninstall)
* [Troubleshooting](#troubleshooting)
* [Requirements](#requirements)
* [File Structure](#file-structure)
* [License](#license)
* [Contributing](#contributing)

---

## Quick Start

### 1. Install Pathman (one-time setup)

```cmd
python pathman.py install
```

This will:

* Create `%USERPROFILE%\.pathman\bin\` and add it to your **user PATH**
* Generate `pathman.bat` to run Pathman from any CMD window
* Create the config file `%USERPROFILE%\.pathman\config.json`

> ⚠️ Open a **new** CMD window after installing for PATH changes to take effect.

---

### 2. Register a Script

```cmd
pathman add myscript.py --alias mycmd
```

Now you can run it from any directory:

```cmd
mycmd.bat               # runs myscript.py
mycmd --help            # passes args through
mycmd input.txt         # arguments forwarded automatically
```

Pathman auto-detects interpreters based on file extension (`.py` → `python`, `.js` → `node`, etc.), but you can override with `--interpreter`.

---

## Commands

| Command                               | Description                                            |
| ------------------------------------- | ------------------------------------------------------ |
| `pathman install`                     | One-time setup, creates launchers and updates PATH     |
| `pathman add <script> --alias <name>` | Register a script as a CMD command                     |
| `pathman list`                        | Show all registered aliases with status                |
| `pathman remove <alias>`              | Unregister an alias and delete its launcher            |
| `pathman edit <alias> [options]`      | Modify an alias: rename, change script, or interpreter |
| `pathman config`                      | Open the configuration file in your default editor     |
| `pathman uninstall`                   | Remove Pathman from PATH and delete all launchers      |

---

## Examples

```cmd
# Register Python script
pathman add C:\Scripts\deck.py --alias deck

# Register JavaScript with node
pathman add tools\converter.js --alias conv --interpreter node

# Register PowerShell script
pathman add backup.ps1 --alias backup --interpreter "powershell -File"

# Rename an alias
pathman edit deck --new-alias deckv2

# Change the script path
pathman edit deck --script C:\new\path\deck.py

# View all registered aliases
pathman list

# Remove an alias
pathman remove deck
```

---

## How It Works

```
pathman add deck.py --alias deck
         │
         ▼
Creates: %USERPROFILE%\.pathman\bin\deck.bat
         │
         └── Contents: python "C:\full\path\to\deck.py" %*

%USERPROFILE%\.pathman\bin\ is in your PATH
         │
         ▼
CMD finds deck.bat when you type: deck [args]
```

Each alias is a `.bat` file that calls the appropriate interpreter with all arguments forwarded.

---

## Supported Interpreters (auto-detected)

| Extension | Default Interpreter |
| --------- | ------------------- |
| `.py`     | `python`            |
| `.js`     | `node`              |
| `.rb`     | `ruby`              |
| `.pl`     | `perl`              |
| `.sh`     | `bash`              |
| `.ps1`    | `powershell -File`  |
| other     | `python`            |

Override with `--interpreter` to run scripts with custom programs.

---

## Configuration

Pathman stores all aliases in:

```
%USERPROFILE%\.pathman\config.json
```

You can edit it manually or with:

```cmd
pathman config
```

Structure:

```json
{
  "aliases": {
    "deck": {
      "script": "C:\\Scripts\\deck.py",
      "interpreter": "python"
    }
  }
}
```

---

## Uninstall

```cmd
pathman uninstall
```

Removes `.pathman\bin` from your PATH and deletes all launchers. Your `config.json` is preserved for reference.

---

## Troubleshooting

**Alias runs but shows no output**

* Interpreter not installed or missing in PATH
* Wrong interpreter used
* Script path is invalid

Fix:

```cmd
pathman edit mycmd --interpreter "C:\Path\To\python.exe"
```

**Command not recognized**

* Restart CMD after installation
* Confirm `%USERPROFILE%\.pathman\bin` is in PATH

**Script shows as MISSING**

* File was moved or deleted
* Update path: `pathman edit mycmd --script newpath`

---

## Requirements

* Windows 10 or 11
* Python 3.8+
* No admin rights required (user PATH only)

---

## File Structure

```
%USERPROFILE%\.pathman/
├── bin/           # .bat launchers for aliases
├── config.json    # alias registry
```



---

## Contributing

* Open issues for bugs or feature requests
* Submit pull requests for improvements
* Keep the tool simple and focused
