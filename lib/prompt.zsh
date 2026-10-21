# Bacumi prompt · MIT License · Copyright (c) 2026 Bacumi
# Data enters through one parameter expansion, so shell-looking names are never eval'd.
source "${${(%):-%x}:A:h}/probe.zsh"

_bacumi_preexec() {
  typeset -g _bacumi_command_pending=1
  return 0
}

_bacumi_escape() {
  REPLY=${1//[[:cntrl:]]/?}
  REPLY=${REPLY//\%/%%}
  [[ $2 == on ]] && REPLY=${REPLY//\!/!!}
  return 0
}

_bacumi_precmd() {
  local -i last_exit=$?
  local bang_option=$options[promptbang]
  emulate -L zsh
  [[ $_bacumi_command_pending == 0 ]] && last_exit=0
  typeset -g _bacumi_command_pending=0
  local -F _bacumi_developer_probe_deadline=$(( EPOCHREALTIME + 0.18 ))
  local directory=$PWD REPLY git_output line branch='' oid='' dirty=''
  local -i terminal_width=${COLUMNS:-80}
  (( terminal_width < 1 )) && terminal_width=80
  local -i path_width=$(( terminal_width / 3 )) branch_width=$(( terminal_width / 3 ))
  (( path_width < 6 )) && path_width=6
  (( branch_width < 6 )) && branch_width=6
  [[ $PWD == "$HOME" || $PWD == "$HOME/"* ]] && directory="~${PWD#"$HOME"}"
  _bacumi_escape "$directory" "$bang_option"
  directory=$REPLY

  # One Git process per new command prompt; never a process on cursor redraw.
  if (( $+commands[git] )) && [[ ${BACUMI_SHOW_GIT:-1} != 0 ]]; then
    if _bacumi_developer_probe 262144 "$commands[git]" --no-optional-locks -c core.fsmonitor=false status --porcelain=v2 --branch --untracked-files=normal; then
      git_output=$_bacumi_developer_probe_output
      for line in ${(f)git_output}; do
        case $line in
          '# branch.head '*) branch=${line#\# branch.head } ;;
          '# branch.oid '*) oid=${line#\# branch.oid } ;;
          '# '*) ;;
          # Porcelain-v2 branch headers precede file records; one is enough.
          *) dirty='*'; break ;;
        esac
      done
      [[ $branch == '(detached)' ]] && branch="@${oid[1,7]}"
    fi
  fi
  local -A color
  if [[ $TERM == dumb || -n $NO_COLOR || ${BACUMI_COLOR_MODE:-auto} == none ]]; then
    color=(accent '' directory '' git '' error '' muted '' reset '')
  elif [[ ${BACUMI_COLOR_MODE:-auto} == truecolor || ( ${BACUMI_COLOR_MODE:-auto} == auto && ( $COLORTERM == (truecolor|24bit) || $TERM == *direct* ) ) ]]; then
    local role
    for role in ${(k)_bacumi_palette}; do color[$role]="%F{${_bacumi_palette[$role]}}"; done
    color[reset]='%f'
  else
    color=(accent '%F{yellow}' directory '%F{blue}' git '%F{green}' error '%F{red}' muted '%F{white}' reset '%f')
  fi
  _bacumi_prompt="${color[directory]}%${path_width}<..<${directory}%<<${color[reset]}"
  if [[ -n $branch ]]; then
    _bacumi_escape "$branch" "$bang_option"
    _bacumi_prompt+=" ${color[git]}git:%${branch_width}<..<${REPLY}%<<${dirty}${color[reset]}"
  fi
  if (( last_exit )); then
    _bacumi_escape "!${last_exit}" "$bang_option"
    _bacumi_prompt+=" ${color[error]}${REPLY}${color[reset]}"
  fi
  _bacumi_prompt+=" ${color[accent]}>${color[reset]} "
  return 0
}

setopt prompt_subst prompt_percent
autoload -Uz add-zsh-hook
# Clean interactive switches from the developer appearance.
add-zsh-hook -d precmd _bacumi_developer_precmd
add-zsh-hook -d preexec _bacumi_developer_preexec
add-zsh-hook -d precmd _bacumi_precmd
add-zsh-hook precmd _bacumi_precmd
add-zsh-hook -d preexec _bacumi_preexec
add-zsh-hook preexec _bacumi_preexec
typeset -g _bacumi_prompt='> '
PROMPT='${_bacumi_prompt}'
RPROMPT=''
