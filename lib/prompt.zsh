# Bacumi prompt · MIT License · Copyright (c) 2026 Bacumi
# Data enters through one parameter expansion, so shell-looking names are never eval'd.
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
    git_output=$(command git --no-optional-locks -c core.fsmonitor=false status --porcelain=v2 --branch --untracked-files=normal 2>/dev/null)
    if (( $? == 0 )); then
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
  if [[ $TERM == dumb || ${BACUMI_COLOR_MODE:-auto} == none ]]; then
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
add-zsh-hook -d precmd _bacumi_precmd
add-zsh-hook precmd _bacumi_precmd
typeset -g _bacumi_prompt='> '
PROMPT='${_bacumi_prompt}'
RPROMPT=''
