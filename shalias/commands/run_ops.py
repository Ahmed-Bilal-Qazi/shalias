"""
shalias run, doctor
"""
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from ..colors import _g, _r, _y
from ..config import backup_config, load_config, save_config
from ..constants import BIN_DIR, IS_WINDOWS
from ..launcher import remove_launcher


def cmd_run(args):
    cfg      = load_config()
    parallel = getattr(args, "parallel", False)
    group    = getattr(args, "group", None)

    if group:
        aliases = sorted(a for a, i in cfg.get("aliases", {}).items()
                         if i.get("group") == group)
        if not aliases:
            print(_r(f"  No aliases in group '{group}'."))
            sys.exit(1)
    else:
        aliases = args.aliases
        if not aliases:
            print(_r("  Nothing to run."))
            print("  Give an alias name, or --group to run a whole group.")
            sys.exit(1)
        for alias in aliases:
            if alias not in cfg["aliases"]:
                print(_r(f"  '{alias}' not found."))
                sys.exit(1)

    def _run_one(alias: str) -> None:
        if not cfg["aliases"].get(alias, {}).get("enabled", True):
            print(_y(f"  Skipping '{alias}' - it's disabled."))
            print(f"  Turn it back on with: shalias edit {alias} --enable")
            return
        launcher = BIN_DIR / (f"{alias}.bat" if IS_WINDOWS else alias)
        if not launcher.exists():
            print(_r(f"  Launcher missing for '{alias}'. Try: shalias doctor --fix"))
            return
        subprocess.run([str(launcher)], check=False)

    if parallel and len(aliases) > 1:
        with ThreadPoolExecutor() as ex:
            list(ex.map(_run_one, aliases))
    else:
        for alias in aliases:
            _run_one(alias)


def cmd_doctor(args):
    cfg     = load_config()
    aliases = cfg.get("aliases", {})
    do_fix  = getattr(args, "fix", False)

    if not aliases:
        print("\n  No aliases registered - nothing to check.\n")
        return

    ok_count = missing_count = warning_count = fixed_count = 0
    to_remove = []

    print("\n  Running diagnostics...\n")
    print(f"  {'ALIAS':<20} {'STATUS':<14} DETAIL")
    print("  " + "-" * 80)

    for alias, info in sorted(aliases.items()):
        atype    = info.get("type", "run")
        target   = info.get("target", "") if atype in ("url", "inline") else info.get("script", "")
        launcher = BIN_DIR / (f"{alias}.bat" if IS_WINDOWS else alias)

        if not launcher.exists():
            print(f"  {alias:<20} {_y('no launcher'):<22}  re-add, or run: shalias doctor --fix")
            warning_count += 1
            continue

        if atype in ("url", "inline", "chain"):
            detail = target[:50] if target else str(info.get("chain", []))
            print(f"  {alias:<20} {_g('ok'):<22}  {detail}")
            ok_count += 1
            continue

        if not target:
            print(f"  {alias:<20} {_r('no target'):<22}  no script path in config")
            warning_count += 1
            continue

        if not Path(target).exists():
            missing_count += 1
            if do_fix:
                to_remove.append(alias)
                print(f"  {alias:<20} {_r('removed'):<22}  {target}")
                fixed_count += 1
            else:
                print(f"  {alias:<20} {_r('missing'):<22}  {target}")
            continue

        if atype == "run":
            interp_bin = (info.get("interpreter", "") or "").split()[0]
            if interp_bin and not shutil.which(interp_bin):
                print(f"  {alias:<20} {_y('no interpreter'):<22}  '{interp_bin}' not found in PATH")
                warning_count += 1
                continue

        print(f"  {alias:<20} {_g('ok'):<22}  {target}")
        ok_count += 1

    if do_fix and to_remove:
        backup_config()
        for alias in to_remove:
            remove_launcher(alias)
            del cfg["aliases"][alias]
        save_config(cfg)

    total = len(aliases)
    print()
    print("  Summary " + "-" * 42)
    print(f"  Checked      : {total}")
    print(f"  {_g('OK')}          : {ok_count}")
    print(f"  Missing      : {missing_count}")
    print(f"  Warnings     : {warning_count}")
    if do_fix:
        print(f"  Fixed        : {fixed_count}")
    if (missing_count or warning_count) and not do_fix:
        print()
        print("  Fix script path  : shalias edit <alias> --script <new-path>")
        print("  Fix interpreter  : shalias edit <alias> --interpreter <cmd>")
        print("  Remove broken    : shalias doctor --fix")
    print()
