# shalias — Cross-Platform Script Alias Manager · v4.0

[![PyPI version](https://img.shields.io/pypi/v/shalias.svg)](https://pypi.org/project/shalias/)
[![Python](https://img.shields.io/pypi/pyversions/shalias.svg)](https://pypi.org/project/shalias/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE.txt)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-blue.svg)]()

Turn any script, file, or URL into a permanent terminal command.

```
shalias add C:\dev\tools\backup.py --alias backup
backup --full
```

That's the whole idea. `backup` now works in every terminal on the machine, forever, from any directory.

---

## Why this exists

On Linux and macOS you can put a line in `.bashrc` and be done. **Windows has no equivalent that survives.** `doskey` dies when the window closes. `Set-Alias` can't pass arguments. Editing the PATH by hand means a registry trip and a new terminal every time you add something.

shalias writes a real launcher into a directory that's already on your PATH, so a new alias works in the shell you're standing in — no restart, no profile editing, no admin rights. It does the same thing on macOS and Linux if you want one habit across all three.

---

## Install

```
pip install shalias
shalias install
```

`pip install` puts the `shalias` command on your PATH. `shalias install` is the one-time step that creates `~/.shalias/bin` and adds *that* to your PATH, which is where your aliases will live.

If you use [pipx](https://pipx.pypa.io):

```
pipx install shalias
shalias install
```

Upgrading later is just `shalias update` — it hands off to whichever one installed you.

---

## Quick start

```
# A script - the interpreter is worked out from the extension
shalias add deploy.py

# A file - opens in whatever app your OS uses for it
shalias add specs.pdf --alias specs

# A URL - opens in your browser
shalias add https://github.com/notifications --alias gh

# A shell one-liner
shalias add "git log --oneline -10" --alias gl --inline

# Several aliases as one command
shalias add --chain build test deploy --alias ship
```

Then, from anywhere:

```
deploy --dry-run
specs
gh
gl
ship
```

Arguments pass straight through to the underlying script.

---

## Commands

Thirteen of them. `shalias <command> --help` has the details on any one.

**Everyday**

| Command | What it does |
| --- | --- |
| `add` | Register a script, file, URL, or command |
| `list [term]` | Show your aliases; add a word to filter |
| `run <alias>...` | Run one or more aliases |
| `which <alias>` | Show what an alias points at |
| `edit <alias>` | Change an alias, or lock/disable it |
| `remove <alias>` | Delete an alias |

**Setup**

| Command | What it does |
| --- | --- |
| `install` | One-time setup on this machine |
| `doctor` | Find broken aliases; `--fix` clears them out |
| `update` | Update shalias itself |
| `uninstall` | Remove shalias and every launcher |

**Moving between machines**

| Command | What it does |
| --- | --- |
| `export <file>` | Save all aliases to JSON |
| `import <file>` | Load aliases from JSON (`--dry-run` to preview) |
| `completion` | Print a shell completion script |

---

## Useful flags

**Where a script runs from.** Scripts that use relative paths break when you call them from elsewhere:

```
shalias add tool.py --cwd script      # always run from the script's own folder
shalias add tool.py --cwd C:\data     # always run from a fixed directory
```

**Environment variables** baked into the launcher:

```
shalias add api.py --env API_KEY=abc123 --env DEBUG=1
```

**Groups**, for running related things together:

```
shalias add build.py --group ci
shalias add test.py  --group ci
shalias run --group ci --parallel
```

**Locking**, so an important alias can't be edited or deleted by accident:

```
shalias edit deploy --lock
shalias edit deploy --unlock
```

**Disabling**, when you want an alias out of the way but not gone:

```
shalias edit deploy --disable    # launcher is parked, config is kept
shalias edit deploy --enable     # exactly as it was
```

**Renaming:**

```
shalias edit oldname --new-alias newname
```

---

## Shell completion

```
# PowerShell
shalias completion powershell >> $PROFILE

# bash
shalias completion bash >> ~/.bashrc

# zsh
shalias completion zsh >> ~/.zshrc
```

---

## How it works

```
shalias add app.py
        |
Creates ~/.shalias/bin/app.bat   (or ~/.shalias/bin/app on macOS and Linux)
        |
That directory is on your PATH
        |
app [args...]  ->  python /full/path/to/app.py [args...]
```

Each launcher is a two-line batch or shell script that calls your file. Nothing runs in the background, nothing phones home, and there are no dependencies beyond the standard library.

```
~/.shalias/
  bin/            <- launchers live here, and this is what's on your PATH
  config.json     <- every alias
  backups/        <- rolling snapshots, written before any change
```

---

## Troubleshooting

**"'myalias' is not recognized" right after adding it**

Run `shalias doctor`. If the PATH entry is written but your current terminal hasn't picked it up, it prints the one line that fixes the shell you're in. A new terminal also works.

**The script runs but can't find its own files**

It's using relative paths. Pin it to its own directory:

```
shalias edit myalias --cwd script
```

**An alias stopped working**

```
shalias doctor          # find what moved
shalias doctor --fix    # drop entries whose files are gone
shalias edit myalias --script /new/path/to/script.py
```

**Wrong interpreter**

```
shalias edit myalias --interpreter python3.11
```

---

## Requirements

- Python 3.9+
- Windows, macOS, or Linux
- No admin or root
- No external dependencies

---

## Upgrading from 3.x

Several commands moved under the command they belonged to — `search` is now `list <term>`, `rename` and `freeze` are flags on `edit`, and so on. The [changelog](CHANGELOG.md) has the full mapping.

---

## Contributing

Bug reports and ideas welcome — open an issue. When reporting a problem, include the output of `shalias doctor` along with your OS and Python version.

Keep it lightweight and dependency-free.
