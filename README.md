# shalias — Cross-Platform Script Alias Manager · v3.0

[![PyPI version](https://img.shields.io/pypi/v/shalias.svg)](https://pypi.org/project/shalias/)
[![Python](https://img.shields.io/pypi/pyversions/shalias.svg)](https://pypi.org/project/shalias/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-blue.svg)]()

Run scripts, open files, and launch URLs as permanent terminal commands — on **Windows, macOS, and Linux**. No config files to edit, no PATH gymnastics, no remembering where things live.

---

## What's new in v3.0

- **Auto-detect type** — just point at a file or URL, shalias figures out the rest
- **Inline commands** — alias any shell one-liner, not just scripts
- **Alias chaining** — wire multiple aliases together into one command
- **Env var injection** — bake environment variables directly into a launcher
- **`--cwd` flag** — control which directory a script runs from
- **Clone** — duplicate an alias and tweak it
- **Instant `list`** — the old 4-second network freeze is gone; broken-alias check is now opt-in with `--check`

---

## Quick start

```
# 1. Install (once)
pip install shalias

# 2. Start adding things (no new terminal needed)
shalias add myscript.py                         # type auto-detected
shalias add report.pdf --alias report           # opens with system default app
shalias add https://github.com --alias gh       # opens in browser
shalias add "git log --oneline -10" --alias gl --inline

# 4. Run from anywhere
mycmd
gl
gh
```

---

## Installation

### Option A — pip (recommended)

```
pip install shalias
```

That's it. No extra steps, no new terminal window needed — pip puts `shalias` on your PATH automatically.

To upgrade later:

```
pip install --upgrade shalias
```

### Option B — run directly (no pip)

```
python shalias.py install
```

This creates `~/.shalias/bin/`, drops a `shalias` launcher in it, and adds that directory to your PATH. Open a new terminal window once it's done.

---

## Adding aliases

The `--type` flag is optional — shalias detects it automatically:

| Target | Detected as |
|---|---|
| `https://...` | `url` |
| `.py .js .rb .sh ...` | `run` |
| `.pdf .docx .png ...` | `open` |

```
# Run a script (interpreter auto-detected)
shalias add app.py

# Override the interpreter
shalias add app.py --interpreter python3.11

# Open a file with the system default app
shalias add ~/reports/q3.pdf --alias q3

# Open a URL
shalias add https://github.com --alias gh

# Inline shell command (anything that works in bash/cmd)
shalias add "git status && git log --oneline -5" --alias gst --inline

# With a custom alias name and description
shalias add deploy.py --alias deploy --description "push to prod"

# Assign to a group
shalias add build.py --alias build --group devops
```

### Working directory

By default, the script runs from wherever you call the alias (current directory). Use `--cwd` to change that:

```
# Always run from the script's own folder
shalias add app.py --cwd script

# Always run from a specific directory
shalias add app.py --cwd /home/me/projects/myapp

# Explicit default (same as not setting it)
shalias add app.py --cwd current
```

### Environment variables

Bake env vars into the launcher so they're always set when the alias runs:

```
shalias add server.py --alias dev --env PORT=8080 --env DEBUG=true
```

Multiple `--env` flags are supported.

---

## Chaining

Run multiple aliases in sequence with a single command:

```
shalias chain release --run test build deploy
```

Running `release` is now equivalent to running `test`, then `build`, then `deploy` one after the other. All three must already exist as aliases.

---

## Clone

Copy an alias under a new name, then edit it from there:

```
shalias clone deploy deploy-staging
shalias edit deploy-staging --env ENV=staging
```

---

## Commands

| Command | What it does |
|---|---|
| `shalias install` | One-time setup |
| `shalias add` | Register an alias |
| `shalias chain <name> --run a b c` | Create a sequential chain |
| `shalias clone <src> <dst>` | Duplicate an alias |
| `shalias list` | Show all aliases |
| `shalias list --sort uses` | Sort by most used |
| `shalias list --sort recent` | Sort by most recently run |
| `shalias list --check` | Also verify file targets still exist |
| `shalias search <term>` | Search by name, path, group, or description |
| `shalias run <alias>` | Run an alias by name |
| `shalias run a b c --parallel` | Run multiple aliases at the same time |
| `shalias run-group <group>` | Run all aliases in a group |
| `shalias edit <alias>` | Modify an alias (interactive prompt) |
| `shalias rename <old> <new>` | Rename an alias |
| `shalias remove <alias>` | Delete an alias |
| `shalias freeze <alias>` | Lock against edits |
| `shalias unfreeze <alias>` | Unlock |
| `shalias stats` | Usage counts and last-run timestamps |
| `shalias doctor` | Check for broken aliases |
| `shalias doctor --fix` | Auto-remove aliases with missing files |
| `shalias export <file>` | Save config to JSON |
| `shalias import <file>` | Load config from JSON |
| `shalias import <file> --dry-run` | Preview import without applying it |
| `shalias update` | Pull the latest version from GitHub |
| `shalias completion bash` | Print bash completion script |
| `shalias completion zsh` | Print zsh completion script |
| `shalias config` | Open config.json in your editor |
| `shalias uninstall` | Remove from PATH and delete launchers |

---

## Editing aliases

Running `shalias edit <alias>` with no extra flags drops into an interactive prompt — just hit Enter to keep any field as-is, or type a new value:

```
$ shalias edit myapp

  Editing: myapp
  Hit Enter to keep current value. Space + Enter to clear.

  alias name       [myapp]:
  type             [run]:
  script path      [/home/me/scripts/app.py]: /home/me/scripts/app_v2.py
  interpreter      [python3]:
  description      [my app]:
  group            [none]:
  cwd              [none]: script
```

Or use flags directly if you know what you want:

```
shalias edit myapp --script /new/path/app.py
shalias edit myapp --interpreter python3.11
shalias edit myapp --env DB_URL=postgres://localhost/dev
```

---

## Groups

Group related aliases together so you can list or run them as a set:

```
shalias add test.py  --alias test  --group dev
shalias add build.py --alias build --group dev
shalias add lint.py  --alias lint  --group dev

shalias list --group dev
shalias run-group dev
```

---

## Locking

Prevent an alias from being accidentally edited or removed:

```
shalias freeze deploy
shalias unfreeze deploy
```

Locked aliases show a 🔒 in the list.

---

## Shell completion

**Bash:**
```
source <(shalias completion bash)
```

Add that line to `~/.bashrc` to make it permanent.

**Zsh:**
```
source <(shalias completion zsh)
```

Add to `~/.zshrc`.

---

## Backup and restore

```
shalias export backup.json
shalias import backup.json
shalias import backup.json --dry-run   # preview first
```

shalias also takes rolling automatic backups (last 10) before any destructive operation. They live in `~/.shalias/backups/`.

---

## Supported interpreters

| Extension | Default interpreter |
|---|---|
| `.py` | `python3` / `python` |
| `.js` | `node` |
| `.ts` | `ts-node` |
| `.sh` | `bash` |
| `.ps1` | `powershell` |
| `.rb` | `ruby` |
| `.pl` | `perl` |
| `.lua` | `lua` |
| `.php` | `php` |
| `.r` / `.R` | `Rscript` |
| `.go` | `go run` |

Override any of these with `--interpreter`:

```
shalias add script.xyz --alias test --interpreter my_custom_runner
```

---

## How it works

```
shalias add app.py
        ↓
Creates ~/.shalias/bin/app  (or app.bat on Windows)
        ↓
That directory is in your PATH
        ↓
app [args...]  →  python3 /full/path/to/app.py [args...]
```

Each launcher is a tiny shell script (or `.bat`) that just calls your actual file. Arguments pass straight through.

---

## File layout

```
~/.shalias/
├── bin/            ← launchers live here (this is on your PATH)
├── config.json     ← all alias data
└── backups/        ← rolling config snapshots
```

---

## Troubleshooting

**Command not found after install**
Restart your terminal, or run `source ~/.bashrc` (or whichever shell config shalias wrote to). On Windows, open a new cmd window.

**Script runs but can't find its own files**
Your script is probably using relative paths. Fix it with:
```
shalias edit myalias --cwd script
```
This makes the script always run from its own directory.

**Alias stopped working**
```
shalias doctor
```
If a file moved, update the path:
```
shalias edit myalias --script /new/path/to/script.py
```

**Wrong interpreter**
```
shalias edit myalias --interpreter python3.11
```

---

## Requirements

- Python 3.8+
- Windows, macOS, or Linux
- No admin/root required
- No external dependencies

---

## Contributing

Bug reports and ideas welcome — open an issue. When reporting a problem, please include the output of `shalias doctor` and your OS + Python version.

Keep it lightweight and dependency-free.
