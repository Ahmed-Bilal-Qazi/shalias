"""
shalias edit — interactive or flag-driven alias editing.
"""
import sys
from pathlib import Path

from ..colors import _b, _d, _g, _r, _y
from ..config import backup_config, load_config, save_config
from ..constants import ALIAS_TYPES
from ..launcher import remove_launcher, write_launcher
from ..utils import parse_env, validate_alias, validate_group, validate_url


def cmd_edit(args):
    cfg   = load_config()
    alias = args.alias

    if alias not in cfg["aliases"]:
        print(_r(f"  '{alias}' not found. Try: shalias list"))
        sys.exit(1)
    if cfg["aliases"][alias].get("locked"):
        print(_r(f"  '{alias}' is locked. Unlock with: shalias unfreeze {alias}"))
        sys.exit(1)

    info  = dict(cfg["aliases"][alias])
    atype = info.get("type", "run")

    # Detect whether we're in interactive mode (no field flags provided)
    field_flags = [
        getattr(args, "new_alias",    None),
        getattr(args, "script",       None),
        getattr(args, "interpreter",  None),
        getattr(args, "description",  None),
        getattr(args, "group",        None),
        getattr(args, "type",         None),
    ]
    interactive = not any(f is not None for f in field_flags)

    if interactive:
        print(f"\n  Editing: {_b(alias)}")
        print(_d("  Hit Enter to keep the current value. Space + Enter to clear.\n"))

        def _prompt(label: str, current: str) -> str:
            val = input(f"  {label:<16} [{current}]: ").strip()
            if val == " ":
                return ""
            return val if val else current

        new_alias_i = _prompt("alias name", alias)

        new_type_i = atype
        while True:
            nt = _prompt("type", atype)
            if nt in ALIAS_TYPES:
                new_type_i = nt
                break
            elif nt == atype:
                break
            print(_y(f"  Options: {', '.join(ALIAS_TYPES)}"))

        if new_type_i in ("url", "inline"):
            new_script_i = _prompt("target", info.get("target", ""))
        else:
            new_script_i = _prompt("script path", info.get("script", ""))

        new_interp_i = ""
        if new_type_i == "run":
            new_interp_i = _prompt("interpreter", info.get("interpreter", ""))

        new_desc_raw  = input(f"  {'description':<16} [{info.get('description', '')}]: ").strip()
        new_desc      = new_desc_raw if new_desc_raw else info.get("description", "")
        if new_desc_raw == " ":
            new_desc = ""

        new_group_raw = input(f"  {'group':<16} [{info.get('group', '') or 'none'}]: ").strip()
        new_group     = new_group_raw if new_group_raw else info.get("group", "")
        if new_group_raw == " ":
            new_group = ""

        new_cwd_raw = input(f"  {'cwd':<16} [{info.get('cwd', '') or 'none'}]: ").strip()
        new_cwd     = new_cwd_raw if new_cwd_raw else info.get("cwd", "")
        if new_cwd_raw == " ":
            new_cwd = ""

        print()
        src_target       = info.get("script", info.get("target", ""))
        args.new_alias   = new_alias_i  if new_alias_i  != alias        else None
        args.type        = new_type_i   if new_type_i   != atype         else None
        args.script      = new_script_i if new_script_i != src_target    else None
        args.interpreter = new_interp_i if new_interp_i != info.get("interpreter", "") else None
        args.description = new_desc
        args.group       = new_group
        args.cwd         = new_cwd

    # ── Apply changes ─────────────────────────────────────────────────────────
    if getattr(args, "type", None) and args.type in ALIAS_TYPES:
        atype       = args.type
        info["type"] = atype

    if getattr(args, "script", None):
        if atype in ("url", "inline"):
            if atype == "url" and not validate_url(args.script):
                print(_r(f"  Not a valid URL: {args.script}"))
                sys.exit(1)
            info["target"] = args.script
            info.pop("script", None)
        else:
            new_script = Path(args.script).resolve()
            if not new_script.exists():
                print(_r(f"  File not found: {new_script}"))
                sys.exit(1)
            info["script"] = str(new_script)
            info.pop("target", None)

    if getattr(args, "interpreter", None) is not None:
        if atype != "run":
            print(_y(f"  --interpreter is ignored for type '{atype}'"))
        else:
            info["interpreter"] = args.interpreter

    if getattr(args, "description", None) is not None:
        info["description"] = args.description

    if getattr(args, "group", None) is not None:
        g = args.group.strip()
        if g and not validate_group(g):
            print(_r(f"  Invalid group name '{g}'"))
            sys.exit(1)
        if g:
            info["group"] = g
        else:
            info.pop("group", None)

    if getattr(args, "cwd", None) is not None:
        info["cwd"] = args.cwd or ""

    if getattr(args, "env", None):
        info["env"] = {**info.get("env", {}), **parse_env(args.env)}

    # ── Handle rename within edit ─────────────────────────────────────────────
    new_alias = getattr(args, "new_alias", None) or alias
    remove_launcher(alias)

    if new_alias != alias:
        if not validate_alias(new_alias):
            print(_r(f"  Invalid alias name '{new_alias}'"))
            sys.exit(1)
        if new_alias in cfg["aliases"]:
            print(_r(f"  '{new_alias}' already exists."))
            sys.exit(1)
        del cfg["aliases"][alias]

    backup_config()
    cfg["aliases"][new_alias] = info
    save_config(cfg)
    write_launcher(new_alias, info)

    label = f"'{alias}'" + (f" -> '{new_alias}'" if new_alias != alias else "")
    print(_g(f"  + Updated {label}"))

    # Show the updated list
    from .list_search import cmd_list

    class _Args:
        group = None
        format = "table"
        json   = False
        sort   = None
        check  = False

    cmd_list(_Args())
