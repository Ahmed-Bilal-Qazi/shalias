"""
shalias which - show what an alias points at and which file backs it.
"""
import sys

from ..colors import _b, _d, _r, _y
from ..config import load_config
from ..launcher import launcher_paths


def cmd_which(args):
    cfg   = load_config()
    alias = args.alias

    if alias not in cfg.get("aliases", {}):
        print(_r(f"  '{alias}' not found. Try: shalias list"))
        sys.exit(1)

    info   = cfg["aliases"][alias]
    atype  = info.get("type", "run")
    live, parked = launcher_paths(alias)

    print()
    print(_b(f"  {alias}"))
    print(f"    type        : {atype}")

    if atype == "chain":
        print(f"    runs        : {' -> '.join(info.get('chain', []))}")
    elif atype in ("url", "inline"):
        print(f"    target      : {info.get('target', '')}")
    else:
        print(f"    script      : {info.get('script', '')}")
        if atype == "run":
            print(f"    interpreter : {info.get('interpreter', '')}")

    for label, key in (("env", "env"), ("cwd", "cwd"),
                       ("group", "group"), ("description", "description")):
        val = info.get(key)
        if not val:
            continue
        if key == "env":
            val = " ".join(f"{k}={v}" for k, v in val.items())
        print(f"    {label:<12}: {val}")

    if info.get("locked"):
        print(f"    {'locked':<12}: yes")

    if not info.get("enabled", True):
        print(f"    {'status':<12}: {_y('disabled')}")
        print(f"    {'launcher':<12}: {parked} {_d('(parked)')}")
        print(f"\n  Turn it back on: shalias edit {alias} --enable\n")
        return

    if live.exists():
        print(f"    {'launcher':<12}: {live}")
    else:
        print(f"    {'launcher':<12}: {_r('missing')}")
        print(f"\n  Rebuild it with: shalias doctor --fix\n")
        return

    suffix = " [args...]" if atype in ("run", "inline") else ""
    print(f"\n  Run it from anywhere: {_b(alias)}{suffix}\n")
