"""
shalias completion (bash / zsh / fish / powershell)
"""
from ..config import load_config


def cmd_completion(args):
    shell   = args.shell.lower()
    aliases = list(load_config().get("aliases", {}).keys())
    names   = " ".join(aliases)

    if shell == "bash":
        print(_bash_completion(names))
    elif shell == "zsh":
        print(_zsh_completion(names))
    elif shell == "fish":
        print(_fish_completion(aliases))
    elif shell in ("powershell", "pwsh"):
        print(_powershell_completion(aliases))
    else:
        from ..colors import _r
        print(_r(f"  Unknown shell '{shell}'. Options: bash, zsh, fish, powershell"))


# Commands that take an alias name as their first argument.
_ALIAS_ARG_CMDS = "run edit remove which"


def _cmds() -> str:
    """The real command list, so completions can't drift from the parser."""
    from ..cli import COMMANDS
    return " ".join(sorted(COMMANDS))


def _bash_completion(names: str) -> str:
    return f"""# shalias bash completion
# Add to ~/.bashrc:  source <(shalias completion bash)
_shalias_complete() {{
  local cur="${{COMP_WORDS[COMP_CWORD]}}"
  local cmds="{_cmds()}"
  local aliases="{names}"
  if [ "${{COMP_CWORD}}" -eq 1 ]; then
    COMPREPLY=( $(compgen -W "$cmds" -- "$cur") )
  else
    COMPREPLY=( $(compgen -W "$aliases" -- "$cur") )
  fi
}}
complete -F _shalias_complete shalias"""


def _zsh_completion(names: str) -> str:
    return f"""# shalias zsh completion
# Add to ~/.zshrc:  source <(shalias completion zsh)
_shalias() {{
  local -a cmds aliases
  cmds=({_cmds()})
  aliases=({names})
  _arguments '1:command:($cmds)' '2:alias:($aliases)'
}}
compdef _shalias shalias"""


def _fish_completion(aliases: list) -> str:
    lines = ["# shalias fish completion",
             "# Add to ~/.config/fish/config.fish: shalias completion fish | source"]
    for cmd in _cmds().split():
        lines.append(f"complete -c shalias -f -n '__fish_use_subcommand' -a {cmd}")
    for alias in aliases:
        lines.append(
            f"complete -c shalias -f -n "
            f"'__fish_seen_subcommand_from {_ALIAS_ARG_CMDS}' -a {alias}"
        )
    return "\n".join(lines)


def _powershell_completion(aliases: list) -> str:
    cmds  = _cmds().split()
    alias_str = ", ".join(f'"{a}"' for a in aliases)
    cmd_str   = ", ".join(f'"{c}"' for c in cmds)
    return f"""# shalias PowerShell completion
# Add to your $PROFILE:  shalias completion powershell | Invoke-Expression
Register-ArgumentCompleter -Native -CommandName shalias -ScriptBlock {{
    param($wordToComplete, $commandAst, $cursorPosition)
    $cmds    = @({cmd_str})
    $aliases = @({alias_str})
    $tokens  = $commandAst.CommandElements
    if ($tokens.Count -le 2) {{
        $cmds | Where-Object {{ $_ -like "$wordToComplete*" }} |
            ForEach-Object {{ [System.Management.Automation.CompletionResult]::new($_, $_, 'ParameterValue', $_) }}
    }} else {{
        $aliases | Where-Object {{ $_ -like "$wordToComplete*" }} |
            ForEach-Object {{ [System.Management.Automation.CompletionResult]::new($_, $_, 'ParameterValue', $_) }}
    }}
}}"""
