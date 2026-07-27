"""
add, chain, clone, remove, rename, freeze, unfreeze
"""
import sys

from ..colors import _g, _r, _y
from ..config import backup_config, load_config, save_config
from ..constants import ALIAS_TYPES
from ..launcher import remove_launcher, write_launcher
from ..utils import (
    check_alias_free,
    detect_interpreter,
    detect_type,
    parse_env,
    print_alias_summary,
    validate_alias,
    validate_group,
    validate_url,
    check_update_async,
)
from pathlib import Path


def cmd_add(args):
    cfg = load_config()
    check_update_async(cfg)

    # ── inline command ────────────────────────────────────────────────────────
    if getattr(args, "inline", False):
        alias = args.alias
        if not alias:
            print(_r("  --alias is required for inline commands."))
            sys.exit(1)
        check_alias_free(alias, cfg)
        entry = {
            "type":        "inline",
            "target":      args.script,
            "description": args.description or "",
            "env":         parse_env(getattr(args, "env", None) or []),
            "cwd":         getattr(args, "cwd", "") or "",
            "use_count":   0,
        }
        if getattr(args, "group", None):
            entry["group"] = args.group
        cfg["aliases"][alias] = entry
        save_config(cfg)
        launcher = write_launcher(alias, entry)
        print_alias_summary(alias, entry, launcher)
        return

    # ── auto-detect type ──────────────────────────────────────────────────────
    raw   = args.script
    atype = (getattr(args, "type", None) or detect_type(raw)).lower()
    if atype not in ALIAS_TYPES:
        print(_r(f"  Unknown type '{atype}'. Options: {', '.join(ALIAS_TYPES)}"))
        sys.exit(1)

    group = (getattr(args, "group", None) or "").strip()
    if group and not validate_group(group):
        print(_r(f"  Invalid group name '{group}'."))
        print("  Letters, numbers, hyphens, and underscores only.")
        sys.exit(1)

    # ── URL ───────────────────────────────────────────────────────────────────
    if atype == "url":
        if not validate_url(raw):
            print(_r(f"  Doesn't look like a URL: {raw}"))
            print("  URLs need to start with http:// or https://")
            sys.exit(1)
        alias = args.alias
        if not alias:
            print(_r("  --alias is required for URL aliases."))
            sys.exit(1)
        check_alias_free(alias, cfg)
        entry = {
            "type": "url", "target": raw,
            "description": args.description or "",
            "use_count": 0, "env": {}, "cwd": "",
        }
        if group:
            entry["group"] = group
        cfg["aliases"][alias] = entry
        save_config(cfg)
        launcher = write_launcher(alias, entry)
        print_alias_summary(alias, entry, launcher)
        return

    # ── file-based (run / open) ───────────────────────────────────────────────
    script = Path(raw).resolve()
    if not script.exists():
        print(_r(f"  File not found: {script}"))
        if " " in raw:
            print(f'  Tip: quote paths with spaces: shalias add "{raw}" ...')
        elif not Path(raw).suffix:
            print("  If this is a shell command, use --inline instead.")
        sys.exit(1)

    alias = args.alias or script.stem
    check_alias_free(alias, cfg)

    base = {
        "description": args.description or "",
        "use_count":   0,
        "env":         parse_env(getattr(args, "env", None) or []),
        "cwd":         getattr(args, "cwd", "") or "",
    }
    if group:
        base["group"] = group

    if atype == "open":
        entry = {**base, "type": "open", "script": str(script)}
    else:
        interp = getattr(args, "interpreter", None) or detect_interpreter(script)
        entry  = {**base, "type": "run", "script": str(script), "interpreter": interp}

    cfg["aliases"][alias] = entry
    save_config(cfg)
    launcher = write_launcher(alias, entry)
    print_alias_summary(alias, entry, launcher)


def cmd_chain(args):
    cfg     = load_config()
    name    = args.name
    steps   = args.run
    check_alias_free(name, cfg)

    missing = [s for s in steps if s not in cfg["aliases"]]
    if missing:
        print(_r(f"  These aliases don't exist yet: {', '.join(missing)}"))
        print("  Add them first, then chain them.")
        sys.exit(1)

    entry = {
        "type":        "chain",
        "chain":       steps,
        "description": args.description or "",
        "use_count":   0,
        "env":         {},
        "cwd":         "",
    }
    if getattr(args, "group", None):
        entry["group"] = args.group

    cfg["aliases"][name] = entry
    save_config(cfg)
    launcher = write_launcher(name, entry)
    print_alias_summary(name, entry, launcher)


def cmd_clone(args):
    cfg = load_config()
    src = args.source
    dst = args.dest

    if src not in cfg["aliases"]:
        print(_r(f"  '{src}' doesn't exist. Nothing to clone."))
        sys.exit(1)
    check_alias_free(dst, cfg)

    entry = dict(cfg["aliases"][src])
    entry["use_count"] = 0
    entry.pop("last_used", None)

    cfg["aliases"][dst] = entry
    save_config(cfg)
    launcher = write_launcher(dst, entry)
    print(_g(f"\n  + Cloned '{src}' -> '{dst}'"))
    print(f"    Tweak it with: shalias edit {dst}\n")


def cmd_remove(args):
    cfg   = load_config()
    alias = args.alias

    if alias not in cfg["aliases"]:
        print(_r(f"  '{alias}' not found. Try: shalias list"))
        sys.exit(1)
    if cfg["aliases"][alias].get("locked"):
        print(_r(f"  '{alias}' is locked. Unlock it first: shalias unfreeze {alias}"))
        sys.exit(1)

    backup_config()
    remove_launcher(alias)
    del cfg["aliases"][alias]
    save_config(cfg)
    print(_g(f"  + Removed '{alias}'"))


def cmd_rename(args):
    cfg = load_config()
    old = args.old_alias
    new = args.new_alias

    if old not in cfg["aliases"]:
        print(_r(f"  '{old}' not found."))
        sys.exit(1)
    if new in cfg["aliases"]:
        print(_r(f"  '{new}' already exists."))
        sys.exit(1)
    if not validate_alias(new):
        print(_r(f"  '{new}' isn't a valid name."))
        sys.exit(1)

    backup_config()
    entry = cfg["aliases"].pop(old)
    cfg["aliases"][new] = entry
    remove_launcher(old)
    write_launcher(new, entry)
    save_config(cfg)
    print(_g(f"  + Renamed '{old}' -> '{new}'"))


def cmd_freeze(args):
    cfg   = load_config()
    alias = args.alias
    if alias not in cfg["aliases"]:
        print(_r(f"  '{alias}' not found."))
        sys.exit(1)
    cfg["aliases"][alias]["locked"] = True
    save_config(cfg)
    print(_g(f"  + '{alias}' is now locked"))


def cmd_unfreeze(args):
    cfg   = load_config()
    alias = args.alias
    if alias not in cfg["aliases"]:
        print(_r(f"  '{alias}' not found."))
        sys.exit(1)
    cfg["aliases"][alias].pop("locked", None)
    save_config(cfg)
    print(_g(f"  + '{alias}' is unlocked"))
