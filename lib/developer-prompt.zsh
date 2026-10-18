# Bacumi native developer prompt · MIT License · Copyright (c) 2026 Bacumi
# All external text is escaped at the rendering boundary, never evaluated.
_bacumi_developer_escape() {
  REPLY=${1//[[:cntrl:]]/?}
  # Directional and zero-width controls can conceal command/path text.
  REPLY=${REPLY//[$'\u061c'$'\u200b'-$'\u200f'$'\u2028'-$'\u202e'$'\u2060'-$'\u206f'$'\ufeff']/?}
  REPLY=${REPLY//\%/%%}
  [[ $_bacumi_developer_bang == on ]] && REPLY=${REPLY//\!/!!}
  return 0
}

# Public-to-tests semantic state: empty ahead/behind means no local upstream data.
_bacumi_developer_parse_git() {
  emulate -L zsh
  local record xy oid='' data=$1
  local -a records
  local -i skip=0
  _bacumi_developer_git=(branch '' unborn 0 detached 0 staged 0 unstaged 0 untracked 0 conflicts 0 ahead '' behind '')
  if [[ $data == *$'\0'* ]]; then records=("${(@0)data}"); else records=("${(@f)data}"); fi
  for record in "${records[@]}"; do
    if (( skip )); then skip=0; continue; fi
    case $record in
      '# branch.oid '*) oid=${record#\# branch.oid }; [[ $oid == '(initial)' ]] && _bacumi_developer_git[unborn]=1 ;;
      '# branch.head '*) _bacumi_developer_git[branch]=${record#\# branch.head } ;;
      '# branch.ab '*)
        local counts=${record#\# branch.ab }
        local ahead=${${counts%% *}#+} behind=${${counts##* }#-}
        if [[ $ahead == <-> && $behind == <-> ]]; then
          _bacumi_developer_git[ahead]=$ahead; _bacumi_developer_git[behind]=$behind
        fi ;;
      '1 '*|'2 '*)
        xy=${record[3,4]}
        [[ $xy[1] != '.' ]] && (( _bacumi_developer_git[staged]++ ))
        [[ $xy[2] != '.' ]] && (( _bacumi_developer_git[unstaged]++ ))
        [[ $record == '2 '* && $data == *$'\0'* ]] && skip=1 ;;
      'u '*) (( _bacumi_developer_git[conflicts]++ )) ;;
      '? '*) (( _bacumi_developer_git[untracked]++ )) ;;
    esac
  done
  if [[ ${_bacumi_developer_git[branch]} == '(detached)' ]]; then
    _bacumi_developer_git[branch]=${oid[1,7]}; _bacumi_developer_git[detached]=1
  fi
  return 0
}

# Resolve Git metadata using files, keeping Git itself to one status process.
_bacumi_developer_operation() {
  emulate -L zsh
  local directory=$PWD gitdir='' entry
  REPLY=''
  if [[ -n $GIT_DIR ]]; then
    gitdir=${GIT_DIR:A}
  else
    while [[ $directory != / ]]; do
      if [[ -d $directory/.git ]]; then gitdir=$directory/.git; break; fi
      if [[ -f $directory/.git ]]; then
        IFS= read -r entry < "$directory/.git"
        [[ $entry == 'gitdir: '* ]] && gitdir=${entry#gitdir: }
        [[ $gitdir != /* ]] && gitdir=$directory/$gitdir
        break
      fi
      directory=${directory:h}
    done
  fi
  [[ -n $gitdir ]] || return 0
  if [[ -d $gitdir/rebase-merge || -d $gitdir/rebase-apply ]]; then REPLY=rebase
  elif [[ -f $gitdir/MERGE_HEAD ]]; then REPLY=merge
  fi
  return 0
}

# Project discovery and version probes never source manifests or activation files.
# zstat includes inode, mtime, ctime and size; TTL also catches replaced tools.
_bacumi_developer_runtimes() {
  emulate -L zsh
  local version_file_text
  local directory=$PWD root='' file signature='' kind executable version cachekey
  local -a kinds files context
  local -A metadata
  REPLY=''
  [[ ${BACUMI_SHOW_RUNTIMES:-1} != 0 ]] || return 0
  while true; do
    kinds=(); files=()
    for file in package.json .node-version .nvmrc; do [[ -f $directory/$file ]] && { kinds+=(node); files+=($directory/$file); }; done
    for file in pyproject.toml requirements.txt setup.py .python-version Pipfile; do [[ -f $directory/$file ]] && { kinds+=(python); files+=($directory/$file); }; done
    [[ -f $directory/go.mod ]] && { kinds+=(go); files+=($directory/go.mod); }
    [[ -f $directory/Cargo.toml || -f $directory/rust-toolchain || -f $directory/rust-toolchain.toml ]] && { kinds+=(rust); files+=($directory/Cargo.toml $directory/rust-toolchain $directory/rust-toolchain.toml); }
    local -a dotnet_files=($directory/*.csproj(N) $directory/*.fsproj(N) $directory/*.sln(N) $directory/*.slnx(N) $directory/global.json(N))
    (( $#dotnet_files )) && { kinds+=(dotnet); files+=("${dotnet_files[@]}"); }
    if (( $#kinds )); then root=$directory; break; fi
    [[ $directory == / ]] && break
    directory=${directory:h}
  done
  [[ -n $VIRTUAL_ENV || -n $CONDA_PREFIX ]] && kinds+=(python)
  for file in "${files[@]}"; do
    if zstat -H metadata -- "$file" 2>/dev/null; then signature+="$file:$metadata[inode]:$metadata[mtime]:$metadata[ctime]:$metadata[size];"
      case ${file:t} in
        .node-version|.nvmrc|.python-version|rust-toolchain|rust-toolchain.toml|global.json)
          version_file_text=''
          IFS= read -r -k 512 version_file_text < "$file" 2>/dev/null
          signature+="$version_file_text;" ;;
      esac fi
  done
  local -i ttl=${BACUMI_RUNTIME_CACHE_SECONDS:-300}
  (( ttl < 1 )) && ttl=300
  for kind in ${(u)kinds}; do
    case $kind in
      node) executable=${commands[node]} ;;
      python) executable=${commands[python3]:-${commands[python]}} ;;
      go) executable=${commands[go]} ;;
      rust) executable=${commands[rustc]} ;;
      dotnet) executable=${commands[dotnet]} ;;
    esac
    [[ -n $executable ]] || continue
    cachekey="$kind|$PWD|$root|$PATH|$executable|$VIRTUAL_ENV|$CONDA_PREFIX|$PYENV_VERSION|$RUSTUP_TOOLCHAIN|$DOTNET_ROOT|$signature"
    if [[ ${_bacumi_developer_cache_key[$kind]} != $cachekey ]] || (( EPOCHSECONDS - ${_bacumi_developer_cache_time[$kind]:-0} >= ttl )); then
      case $kind in
        node|python|rust|dotnet) version=$("$executable" --version 2>/dev/null) ;;
        go) version=$("$executable" version 2>/dev/null) ;;
      esac
      # Bound output and accept only the version token, not arbitrary tool banners.
      version=${version%%$'\n'*}
      case $kind in
        node) version=${version#v} ;;
        python) version=${version#Python } ;;
        go) version=${${version#go version go}%% *} ;;
        rust) version=${${version#rustc }%% *} ;;
      esac
      [[ $version == [0-9]* && $version != *[[:cntrl:]]* && ${#version} -le 40 ]] || version=''
      _bacumi_developer_cache_key[$kind]=$cachekey
      _bacumi_developer_cache_version[$kind]=$version
      _bacumi_developer_cache_time[$kind]=$EPOCHSECONDS
    fi
    version=${_bacumi_developer_cache_version[$kind]}
    [[ -n $version ]] && context+=("$kind:$version")
  done
  local environment=${VIRTUAL_ENV:-$CONDA_PREFIX}
  [[ -n $environment ]] && context+=("venv:${environment:t}")
  REPLY="${(j:  :)context}"
  return 0
}

_bacumi_developer_preexec() {
  _bacumi_developer_started=$EPOCHREALTIME
  return 0
}

_bacumi_developer_precmd() {
  local -i last_exit=$?
  local _bacumi_developer_bang=$options[promptbang]
  emulate -L zsh
  local -F elapsed=0
  [[ -n $_bacumi_developer_started ]] && elapsed=$(( EPOCHREALTIME - _bacumi_developer_started ))
  _bacumi_developer_started=''
  local directory=$PWD branch='' git_output operation='' runtimes='' result='' duration='' context='' REPLY
  local -i width=${COLUMNS:-80} jobs_count=${#jobstates}
  (( width < 1 )) && width=80
  [[ $PWD == "$HOME" || $PWD == "$HOME/"* ]] && directory="~${PWD#"$HOME"}"
  _bacumi_developer_parse_git ''
  if (( $+commands[git] )) && [[ ${BACUMI_SHOW_GIT:-1} != 0 ]]; then
    local untracked=normal
    [[ ${BACUMI_GIT_DETAILS:-1} == 0 ]] && untracked=no
    git_output=$(command git --no-optional-locks -c core.fsmonitor=false status --porcelain=v2 -z --branch --ignore-submodules=dirty --untracked-files=$untracked 2>/dev/null)
    if (( $? == 0 )); then
      _bacumi_developer_parse_git "$git_output"
      branch=${_bacumi_developer_git[branch]}
      (( _bacumi_developer_git[detached] )) && branch="@$branch"
      _bacumi_developer_operation; operation=$REPLY
    fi
  fi
  _bacumi_developer_runtimes; runtimes=$REPLY
  (( last_exit )) && result="!$last_exit"
  if (( elapsed >= 2 )); then printf -v duration '%.1fs' "$elapsed"; fi
  [[ -n $SSH_CONNECTION || -n $SSH_TTY || $EUID == 0 ]] && context="${USER:-${USERNAME:-user}}@${HOST%%.*}"
  (( jobs_count )) && context+="${context:+  }jobs:$jobs_count"

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
  local marker='>' critical='' detail='' firstline='' secondline='' gitcolor=$color[git]
  [[ ${BACUMI_PROMPT_ICONS:-0} == 1 ]] && marker='❯'
  if (( _bacumi_developer_git[conflicts] )); then
    critical="conflict:${_bacumi_developer_git[conflicts]}"; gitcolor=$color[error]
  fi
  if [[ ${BACUMI_GIT_DETAILS:-1} != 0 ]]; then
    (( _bacumi_developer_git[staged] )) && detail+=" +${_bacumi_developer_git[staged]}"
    (( _bacumi_developer_git[unstaged] )) && detail+=" ~${_bacumi_developer_git[unstaged]}"
    (( _bacumi_developer_git[untracked] )) && detail+=" ?${_bacumi_developer_git[untracked]}"
    [[ ${_bacumi_developer_git[ahead]} == <-> ]] && (( _bacumi_developer_git[ahead] )) && detail+=" ahead:${_bacumi_developer_git[ahead]}"
    [[ ${_bacumi_developer_git[behind]} == <-> ]] && (( _bacumi_developer_git[behind] )) && detail+=" behind:${_bacumi_developer_git[behind]}"
  fi
  [[ -n $operation ]] && critical+="${critical:+ }$operation"
  local -i budget=$(( width - 1 )) result_width=0
  if [[ ${BACUMI_PROMPT_LAYOUT:-developer} == compact ]]; then
    result_width=$(( ${#result} + ${#marker} + 2 )); (( budget-=result_width ))
  fi
  local -i critical_width=${#critical} branch_width=0 path_width=$budget
  [[ -n $critical ]] && (( path_width-=critical_width+1 ))
  if [[ -n $branch ]]; then
    branch_width=$(( path_width / 2 - 4 )); (( branch_width < 3 )) && branch_width=3
    (( path_width-=branch_width+5 ))
  fi
  (( path_width < 1 )) && path_width=1
  _bacumi_developer_escape "$directory"
  firstline="${color[directory]}%${path_width}<..<${REPLY}%<<${color[reset]}"
  local -i used=$(( ${(m)#directory} < path_width ? ${(m)#directory} : path_width ))
  if [[ -n $branch ]]; then
    _bacumi_developer_escape "$branch"
    firstline+=" ${gitcolor}git:%${branch_width}<..<${REPLY}%<<${color[reset]}"
    (( used+=5+(${(m)#branch} < branch_width ? ${(m)#branch} : branch_width) ))
  fi
  if [[ -n $critical ]]; then
    _bacumi_developer_escape "$critical"; firstline+=" ${color[error]}$REPLY${color[reset]}"; (( used+=critical_width+1 ))
  fi
  # Lower-priority context is added only as a complete segment that fits.
  local segment
  if (( width > 40 )); then
    for segment in "$detail" "$runtimes" "$context" "$duration"; do
      segment=${segment## }
      if [[ -n $segment ]] && (( used + ${(m)#segment} + 2 <= budget )); then
        _bacumi_developer_escape "$segment"; firstline+="  ${color[muted]}$REPLY${color[reset]}"
        (( used+=${(m)#segment}+2 ))
      fi
    done
  fi
  [[ -n $result ]] && { _bacumi_developer_escape "$result"; secondline="${color[error]}$REPLY${color[reset]} "; }
  secondline+="${color[accent]}$marker${color[reset]} "
  if [[ ${BACUMI_PROMPT_LAYOUT:-developer} == compact ]]; then _bacumi_developer_prompt="$firstline $secondline"
  else _bacumi_developer_prompt="$firstline"$'\n'"$secondline"
  fi
  return 0
}

zmodload zsh/datetime
zmodload zsh/stat
zmodload zsh/parameter
typeset -gA _bacumi_developer_git _bacumi_developer_cache_key _bacumi_developer_cache_version _bacumi_developer_cache_time
typeset -g _bacumi_developer_started _bacumi_developer_prompt
setopt prompt_subst prompt_percent
autoload -Uz add-zsh-hook
# Replace only our own/lightweight hook, retain every unrelated hook.
add-zsh-hook -d precmd _bacumi_precmd
add-zsh-hook -d precmd _bacumi_developer_precmd
add-zsh-hook -d preexec _bacumi_developer_preexec
precmd_functions=(_bacumi_developer_precmd "${precmd_functions[@]}")
add-zsh-hook preexec _bacumi_developer_preexec
_bacumi_developer_prompt='> '
PROMPT='${_bacumi_developer_prompt}'
RPROMPT=''
