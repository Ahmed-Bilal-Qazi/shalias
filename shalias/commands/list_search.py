"""
shalias list, search, stats
"""
import sys

from ..colors import _b, _d, _g, _r, _y
from ..config import load_config, get_command_name
from ..utils import check_update_async, format_aliases, format_stats, resolve_format
from pathlib import Path


def cmd_list(args):
    cfg          = load_config()
    cmd_name     = get_command_name(cfg)
    check_update_async(cfg)

    aliases      = cfg.get("aliases", {})
    group_filter = getattr(args, "group",  None)
    sort_by      = getattr(args, "sort",   None)
    fmt          = resolve_format(args)
    check        = getattr(args, "check",  False)
    type_filter  = getattr(args, "type",   None)

    if group_filter:
        aliases = {k: v for k, v in aliases.items()
                   if v.get("group", "") == group_filter}

    if type_filter:
        aliases = {k: v for k, v in aliases.items()
                   if v.get("type", "") == type_filter}

    if sort_by == "recent":
        aliases = dict(sorted(aliases.items(),
                              key=lambda x: x[1].get("last_used", ""), reverse=True))
    elif sort_by == "uses":
        aliases = dict(sorted(aliases.items(),
                              key=lambda x: x[1].get("use_count", 0), reverse=True))
    else:
        aliases = dict(sorted(aliases.items()))

    if check:
        broken = [
            (a, i.get("script", ""))
            for a, i in aliases.items()
            if i.get("type") == "run" and not Path(i.get("script", "x")).exists()
        ]
        if broken:
            print()
            print(_y("  Some aliases point to missing files:"))
            for a, t in broken:
                print(f"    {a:<20} -> {t}")
            print(f"  Run '{cmd_name} doctor' for the full breakdown.\n")

    if not aliases:
        print()
        if group_filter:
            print(f"  No aliases in group '{group_filter}'.")
        elif type_filter:
            print(f"  No aliases of type '{type_filter}'.")
        else:
            print("  Nothing registered yet.")
            print(f"  Add a script  : {cmd_name} add myscript.py")
            print(f"  Add a URL     : {cmd_name} add https://example.com --alias ex")
            print(f"  Inline command: {cmd_name} add 'git log --oneline -5' --alias gl --inline")
        print()
        return

    format_aliases(aliases, fmt, cmd_name)


def cmd_search(args):
    cfg   = load_config()
    query = args.query.lower().strip()

    if not query:
        print(_r("  Search query can't be empty."))
        sys.exit(1)

    found = {}
    for alias, info in cfg.get("aliases", {}).items():
        haystack = " ".join([
            alias,
            info.get("description", ""),
            info.get("target", ""),
            info.get("script", ""),
            info.get("group", ""),
            info.get("interpreter", ""),
        ]).lower()
        if query in haystack:
            found[alias] = info

    if not found:
        print(f"\n  No results for '{args.query}'.\n")
        return

    fmt = resolve_format(args)
    print(f"\n  {len(found)} result(s) for '{_b(args.query)}':\n")
    format_aliases(found, fmt)


def cmd_stats(args):
    cfg     = load_config()
    aliases = cfg.get("aliases", {})

    if not aliases:
        print("\n  No aliases yet.\n")
        return

    fmt = resolve_format(args)
    format_stats(aliases, fmt)
