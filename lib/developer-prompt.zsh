# Bacumi native developer prompt · MIT License · Copyright (c) 2026 Bacumi
# All external text is escaped at the rendering boundary, never evaluated.

source "${${(%):-%x}:A:h}/probe.zsh"

_bacumi_developer_sanitize() {
  emulate -L zsh
  local character clean='' codepoint
  for character in ${(s::)1}; do
    builtin printf -v codepoint '%d' "'$character"
    if (( codepoint < 32 || (codepoint >= 127 && codepoint <= 159) || codepoint == 0x061c ||
          (codepoint >= 0x200b && codepoint <= 0x200f) || (codepoint >= 0x2028 && codepoint <= 0x202e) ||
          (codepoint >= 0x2060 && codepoint <= 0x206f) || codepoint == 0xfeff )); then clean+='?'
    else clean+=$character
    fi
  done
  REPLY=$clean
  return 0
}

_bacumi_developer_escape() {
  _bacumi_developer_sanitize "$1"
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
  _bacumi_developer_git=(branch '' unborn 0 detached 0 staged 0 unstaged 0 untracked 0 conflicts 0 ahead '' behind '' unavailable 0)
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
  typeset -g _bacumi_developer_git_dir=''
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
  _bacumi_developer_git_dir=$gitdir
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
          IFS= builtin read -r -u 0 -k 512 version_file_text < "$file" 2>/dev/null
          signature+="$version_file_text;" ;;
      esac fi
  done
  local -i ttl=${BACUMI_RUNTIME_CACHE_SECONDS:-300}
  (( ttl < 1 )) && ttl=300
  local -F _bacumi_developer_probe_deadline=${_bacumi_developer_probe_deadline:-$(( EPOCHREALTIME + 0.18 ))}
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
    local -i effective_ttl=$ttl
    [[ -n ${_bacumi_developer_cache_version[$kind]} ]] || effective_ttl=2
    if [[ ${_bacumi_developer_cache_key[$kind]} != $cachekey ]] || (( EPOCHSECONDS - ${_bacumi_developer_cache_time[$kind]:-0} >= effective_ttl )); then
      case $kind in
        node|python|rust|dotnet) _bacumi_developer_probe 4096 "$executable" --version ;;
        go) _bacumi_developer_probe 4096 "$executable" version ;;
      esac
      version=$_bacumi_developer_probe_output
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
  # Empty Enter runs precmd without preexec; do not repeat a stale failure.
  [[ -z $_bacumi_developer_started && $_bacumi_developer_rendered == 1 ]] && last_exit=0
  typeset -g _bacumi_developer_rendered=1
  local -F _bacumi_developer_probe_deadline=$(( EPOCHREALTIME + 0.18 ))
  local -F elapsed=0
  [[ -n $_bacumi_developer_started ]] && elapsed=$(( EPOCHREALTIME - _bacumi_developer_started ))
  _bacumi_developer_started=''
  local directory=$PWD branch='' git_output operation='' runtimes='' result='' duration='' context='' REPLY
  local -i width=${COLUMNS:-80} jobs_count=${#jobstates}
  (( width < 1 )) && width=80
  [[ $PWD == "$HOME" || $PWD == "$HOME/"* ]] && directory="~${PWD#"$HOME"}"
  _bacumi_developer_parse_git ''
  if [[ ${BACUMI_SHOW_GIT:-1} != 0 ]]; then
    local untracked=normal
    [[ ${BACUMI_GIT_DETAILS:-1} == 0 ]] && untracked=no
    local -i git_exit=127
    if (( $+commands[git] )); then
      _bacumi_developer_probe 262144 "$commands[git]" --no-optional-locks -c core.fsmonitor=false status --porcelain=v2 -z --branch --ignore-submodules=dirty --untracked-files=$untracked
      git_exit=$?
      git_output=$_bacumi_developer_probe_output
    fi
    if (( git_exit == 0 )); then
      _bacumi_developer_parse_git "$git_output"
      branch=${_bacumi_developer_git[branch]}
      (( _bacumi_developer_git[detached] )) && branch="@$branch"
      _bacumi_developer_operation; operation=$REPLY
    else
      # A slow/unavailable status must not pretend the checkout is clean or
      # erase its location. HEAD is a small local metadata file, not another Git probe.
      _bacumi_developer_operation; operation=$REPLY
      if [[ -n $_bacumi_developer_git_dir && -f $_bacumi_developer_git_dir/HEAD ]]; then
        local head_text=''
        IFS= builtin read -r -u 0 -k 512 head_text < "$_bacumi_developer_git_dir/HEAD" 2>/dev/null
        local -i head_read=$?
        # Successful read means all 512 requested characters were present;
        # reject a possibly truncated record instead of inventing a branch.
        if (( head_read != 0 )); then
          head_text=${head_text%$'\n'}
          if [[ $head_text == 'ref: refs/heads/'?* ]]; then
            local head_branch=${head_text#ref: refs/heads/}
            [[ $head_branch != *[[:cntrl:][:space:]]* ]] && branch=$head_branch
          elif (( ${#head_text} == 40 || ${#head_text} == 64 )) && [[ $head_text != *[^0-9a-f]* ]]; then branch="@${head_text[1,7]}"
          fi
        fi
        [[ -n $branch ]] && _bacumi_developer_git[unavailable]=1
      fi
    fi
  fi
  _bacumi_developer_runtimes; runtimes=$REPLY
  if (( last_exit )); then
    local failure_label='command failed'
    case $last_exit in
      126) failure_label='cannot execute' ;;
      127) failure_label='command not found' ;;
      130) failure_label='interrupted' ;;
      143) failure_label='terminated' ;;
    esac
    result="!$last_exit $failure_label"
  fi
  if (( elapsed >= 2 )); then printf -v duration '%.1fs' "$elapsed"; fi
  [[ -n $SSH_CONNECTION || -n $SSH_TTY || $EUID == 0 ]] && context="${USER:-${USERNAME:-user}}@${HOST%%.*}"
  (( jobs_count )) && context+="${context:+  }jobs:$jobs_count"

  # Sanitize before measuring so replacement glyphs are included in widths.
  _bacumi_developer_sanitize "$directory"; directory=$REPLY
  _bacumi_developer_sanitize "$branch"; branch=$REPLY
  _bacumi_developer_sanitize "$runtimes"; runtimes=$REPLY
  _bacumi_developer_sanitize "$context"; context=$REPLY
  # Padded, separate Bacumi badges. Width budgets include every space.
  local -A style
  local reset='' marker_style=''
  if [[ $TERM == dumb || -n $NO_COLOR || ${BACUMI_COLOR_MODE:-auto} == none ]]; then
    style=(directory '' git '' context '' error '')
  elif [[ ${BACUMI_COLOR_MODE:-auto} == truecolor || ( ${BACUMI_COLOR_MODE:-auto} == auto && ( $COLORTERM == (truecolor|24bit) || $TERM == *direct* ) ) ]]; then
    style[directory]="%F{$_bacumi_palette[background]}%K{$_bacumi_palette[accent]}"
    style[git]="%F{$_bacumi_palette[background]}%K{$_bacumi_palette[git]}"
    style[context]="%F{$_bacumi_palette[foreground]}%K{$_bacumi_palette[selection]}"
    style[error]="%F{$_bacumi_palette[background]}%K{$_bacumi_palette[error]}"
    marker_style="%F{$_bacumi_palette[accent]}"; reset='%k%f'
  else
    # Reverse against the default surface: ANSI black/white may themselves be
    # accessible text colors, so neither is a reliable contrasting badge ink.
    style=(directory '%F{yellow}%k%S' git '%F{green}%k%S' context '%F{8}%k%S' error '%F{red}%k%S')
    marker_style='%F{yellow}'; reset='%s%k%f'
  fi
  local marker='>' failure='' firstline='' inputline='' gittext='' git_suffix=''
  local layout=${BACUMI_PROMPT_LAYOUT:-developer}
  [[ ${BACUMI_PROMPT_ICONS:-0} == 1 ]] && marker='❯'
  [[ -n $result ]] && failure=$result
  if (( width >= 16 && ${#failure} > width-6 )); then failure="${failure[1,$((width-9))]}..."; fi
  local -i input_width=$(( ${(m)#marker} + 1 ))
  [[ -n $failure ]] && (( input_width+=${(m)#failure}+3 ))
  (( _bacumi_developer_git[conflicts] )) && git_suffix=" conflict:${_bacumi_developer_git[conflicts]}"
  (( _bacumi_developer_git[unavailable] )) && git_suffix+=' status:?'
  local -i minimum_first=3
  [[ -n $branch ]] && (( minimum_first+=8+${(m)#git_suffix} ))
  # Let compact failures wrap before sacrificing their explanation or Git state.
  [[ -n $failure ]] && (( minimum_first+input_width+2 > width )) && layout=developer
  local -i content_width=$(( width - 1 ))
  [[ $layout == compact ]] && (( content_width-=input_width+1 ))
  (( content_width < 8 )) && content_width=8
  if [[ -n $operation ]] && (( content_width >= 11+${(m)#git_suffix}+${(m)#operation} )); then
    git_suffix+=" $operation"
  fi
  local -i fixed_width=2
  [[ -n $branch ]] && (( fixed_width+=7+${(m)#git_suffix} ))
  local -i text_budget=$(( content_width-fixed_width ))
  (( text_budget < 1 )) && text_budget=1
  local -i path_width=${(m)#directory} branch_width=${(m)#branch}
  if [[ -n $branch ]] && (( path_width+branch_width > text_budget )); then
    path_width=$(( text_budget/2 )); (( path_width < 1 )) && path_width=1
    branch_width=$(( text_budget-path_width )); (( branch_width < 1 )) && branch_width=1
    if (( ${(m)#branch} < branch_width )); then (( path_width+=branch_width-${(m)#branch} )); fi
    if (( ${(m)#directory} < path_width )); then (( branch_width+=path_width-${(m)#directory} )); fi
  elif [[ -z $branch ]]; then
    path_width=$text_budget
  fi
  (( path_width > ${(m)#directory} )) && path_width=${(m)#directory}
  (( branch_width > ${(m)#branch} )) && branch_width=${(m)#branch}
  local -i used=$(( path_width+2 ))
  [[ -n $branch ]] && (( used+=branch_width+${(m)#git_suffix}+7 ))
  local -a git_optional context_parts badges
  if [[ ${BACUMI_GIT_DETAILS:-1} != 0 ]] && (( ! _bacumi_developer_git[unavailable] )); then
    (( _bacumi_developer_git[staged] )) && git_optional+=("+${_bacumi_developer_git[staged]}")
    (( _bacumi_developer_git[unstaged] )) && git_optional+=("~${_bacumi_developer_git[unstaged]}")
    (( _bacumi_developer_git[untracked] )) && git_optional+=("?${_bacumi_developer_git[untracked]}")
    [[ ${_bacumi_developer_git[ahead]} == <-> ]] && (( _bacumi_developer_git[ahead] )) && git_optional+=("ahead:${_bacumi_developer_git[ahead]}")
    [[ ${_bacumi_developer_git[behind]} == <-> ]] && (( _bacumi_developer_git[behind] )) && git_optional+=("behind:${_bacumi_developer_git[behind]}")
  fi
  local segment git_details=''
  for segment in "${git_optional[@]}"; do
    if (( used+${(m)#segment}+1 <= content_width )); then
      git_details+=" $segment"; (( used+=${(m)#segment}+1 ))
    fi
  done
  # Runtime labels are admitted separately; a long environment name must not
  # hide an otherwise short active runtime or command duration.
  context_parts=("${(@s:  :)runtimes}" "${(@s:  :)context}" "$duration")
  if (( width >= 80 )); then
    for segment in "${context_parts[@]}"; do
      [[ -n $segment ]] || continue
      local -i needed=$(( used+${(m)#segment}+3-content_width ))
      if (( needed > 0 && path_width-needed >= 7 )); then (( path_width-=needed )); (( used-=needed )); fi
      break
    done
  fi
  if (( ${(m)#directory} > path_width && path_width >= 7 )); then
    directory=".../${directory:t}"
    if (( ${(m)#directory} < path_width )); then
      (( used-=path_width-${(m)#directory} ))
      path_width=${(m)#directory}
    fi
  fi
  _bacumi_developer_escape "$directory"
  local path_ellipsis='..' branch_ellipsis='..'
  (( path_width < 2 )) && path_ellipsis='.'
  (( branch_width < 2 )) && branch_ellipsis='.'
  badges+=("${style[directory]} %${path_width}<${path_ellipsis}<${REPLY}%<< $reset")
  if [[ -n $branch ]]; then
    _bacumi_developer_escape "$branch"
    local git_role=git
    (( _bacumi_developer_git[conflicts] || _bacumi_developer_git[unavailable] )) && git_role=error
    gittext="git:%${branch_width}<${branch_ellipsis}<${REPLY}%<<"
    _bacumi_developer_escape "$git_suffix$git_details"
    badges+=("${style[$git_role]} $gittext$REPLY $reset")
  fi
  for segment in "${context_parts[@]}"; do
    if [[ -n $segment ]] && (( used+${(m)#segment}+3 <= content_width )); then
      _bacumi_developer_escape "$segment"
      badges+=("${style[context]} $REPLY $reset")
      (( used+=${(m)#segment}+3 ))
    fi
  done
  firstline="${(j: :)badges}"
  if [[ -n $failure ]]; then
    _bacumi_developer_escape "$failure"
    inputline="${style[error]} $REPLY $reset "
  fi
  inputline+="$marker_style$marker$reset "
  if [[ $layout == compact ]]; then _bacumi_developer_prompt="$firstline $inputline"
  else _bacumi_developer_prompt="$firstline"$'\n'"$inputline"
  fi
  return 0
}

typeset -g _bacumi_developer_probe_output
typeset -gA _bacumi_developer_git _bacumi_developer_cache_key _bacumi_developer_cache_version _bacumi_developer_cache_time
typeset -g _bacumi_developer_started _bacumi_developer_prompt
setopt prompt_subst prompt_percent
autoload -Uz add-zsh-hook
# Replace only our own/lightweight hook, retain every unrelated hook.
add-zsh-hook -d precmd _bacumi_precmd
add-zsh-hook -d preexec _bacumi_preexec
add-zsh-hook -d precmd _bacumi_developer_precmd
add-zsh-hook -d preexec _bacumi_developer_preexec
precmd_functions=(_bacumi_developer_precmd "${precmd_functions[@]}")
add-zsh-hook preexec _bacumi_developer_preexec
_bacumi_developer_prompt='> '
PROMPT='${_bacumi_developer_prompt}'
RPROMPT=''
