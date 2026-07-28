# Changelog

All notable changes to shalias are recorded here.
This project follows [semantic versioning](https://semver.org/).

## [4.0.0] - 2026-07-29

A consolidation release. Everything 3.0 could do, 4.0 still does - but
through a third as many commands, and without the background network call
that made `list` feel slow.

### Breaking

- **26 commands are now 13.** Nothing was lost except four commands nobody
  needed; the rest moved under a flag on the command they belonged to:

  | 3.0 | 4.0 |
  | --- | --- |
  | `shalias search <term>` | `shalias list <term>` |
  | `shalias run-group <name>` | `shalias run --group <name>` |
  | `shalias rename <a> <b>` | `shalias edit <a> --new-alias <b>` |
  | `shalias freeze` / `unfreeze` | `shalias edit <a> --lock` / `--unlock` |
  | `shalias chain a b c` | `shalias add --chain a b c` |
  | `shalias clone`, `config`, `rename-cmd`, `stats` | removed |

- **`shalias update` no longer downloads anything itself.** It calls pip or
  pipx, whichever installed you. The old updater overwrote its own entry
  point, which broke pip installs outright.
- **The standalone single-file build is gone.** It had drifted a full major
  version behind. Install with `pip` or `pipx`.
- **Python 3.9 is the floor**, up from 3.8.

### Added

- `shalias which <alias>` - what an alias points at, which launcher backs it,
  and whether it's live.
- `shalias edit <alias> --disable` / `--enable` - park an alias without
  deleting it. The launcher moves aside rather than being removed, so
  re-enabling restores exactly what you had.
- `shalias doctor` now checks PATH. If the entry is written but the current
  terminal never picked it up - the usual first-run failure on Windows - it
  prints the one-liner that fixes the shell you're in.
- `shalias list <term>` searches names, descriptions, targets and groups.

### Changed

- `--help` groups commands by what you're trying to do instead of listing
  thirteen of them alphabetically.
- Output is ASCII throughout. Em dashes and bullets turned into mojibake on
  a cp1252 console, which is the default one on Windows.

### Removed

- **Usage tracking.** Every launcher spawned a second Python process to
  increment a counter. On Windows that ran in the foreground: 244ms per
  alias, down to 57ms with it gone. `stats` went with it.
- **The background version check** that ran on `list` and `add`. It compared
  versions with `!=` rather than a version compare, so it happily advertised
  3.0 as an upgrade from 4.0. shalias no longer touches the network unless
  you type `shalias update`.

### Fixed

- The package couldn't be imported after installation - `commands/__init__.py`
  was missing and `io_ops.py` sat one directory too high.
- Disabling or renaming an alias read a stale launcher path, so it could
  leave the old launcher behind.

## [3.0.0] - 2026

Restructured from a single script into a pip-installable package. Added
auto-detected alias types, inline commands, alias chaining, baked-in
environment variables and `--cwd`.

## [2.0.0] - 2026

Renamed from pathman to shalias.

## [1.0.0] - 2026

First release, as pathman.
