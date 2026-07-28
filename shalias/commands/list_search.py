"""
shalias list, search
"""
import sys

from ..colors import _b, _d, _g, _r, _y
from ..config import load_config
from ..utils import format_aliases, resolve_format
from pathlib import Path


def cmd_list(args):
    cfg          = load_config()
    aliases      = cfg.get("aliases", {})
    pattern      = (getattr(args, "pattern", None) or "").lower().strip()
    group_filter = getattr(args, "group",  None)
    sort_by      = getattr(args, "sort",   None)
    fmt          = resolve_format(args)
    check        = getattr(args, "check",  False)
    type_filter  = getattr(args, "type",   None)

    if pattern:
        aliases = {k: v for k, v in aliases.items() if _matches(k, v, pattern)}

    if group_filter:
        aliases = {k: v for k, v in aliases.items()
                   if v.get("group", "") == group_filter}

    if type_filter:
        aliases = {k: v for k, v in aliases.items()
                   if v.get("type", "") == type_filter}

    if sort_by == "recent":
        aliases = dict(sorted(aliases.items(),
                              key=lambda x: x[1].get("added", ""), reverse=True))
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
            print("  Run 'shalias doctor' for the full breakdown.\n")

    if not aliases:
        print()
        if pattern:
            print(f"  Nothing matches '{pattern}'.")
        elif group_filter:
            print(f"  No aliases in group '{group_filter}'.")
        elif type_filter:
            print(f"  No aliases of type '{type_filter}'.")
        else:
            print("  Nothing registered yet.")
            print("  Add a script  : shalias add myscript.py")
            print("  Add a URL     : shalias add https://example.com --alias ex")
            print("  Inline command: shalias add 'git log --oneline -5' --alias gl --inline")
        print()
        return

    format_aliases(aliases, fmt)


def _matches(alias: str, info: dict, needle: str) -> bool:
    """True if *needle* turns up anywhere worth searching on this alias."""
    haystack = " ".join([
        alias,
        info.get("description", ""),
        info.get("target", ""),
        info.get("script", ""),
        info.get("group", ""),
        info.get("interpreter", ""),
    ]).lower()
    return needle in haystack


