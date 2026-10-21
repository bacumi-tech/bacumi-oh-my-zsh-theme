# Bacumi bounded native probes · MIT License · Copyright (c) 2026 Bacumi
zmodload zsh/datetime
zmodload zsh/stat
zmodload zsh/parameter
zmodload zsh/system
zmodload zsh/zpty
zmodload zsh/zselect
# zpty receives only this fixed function name. Arguments stay in a quoted array;
# no directory, branch, environment or command text is evaluated by zpty.
_bacumi_developer_probe_worker() {
  emulate -L zsh
  # This fork is a probe, not a terminal session. Inherited session-saving
  # hooks can write after our exit frame or save a snapshot of worker state.
  builtin unfunction zshexit TRAPEXIT 2>/dev/null
  typeset -ga zshexit_functions=()
  builtin trap - EXIT
  unsetopt monitor 2>/dev/null
  export GIT_TERMINAL_PROMPT=0 GIT_OPTIONAL_LOCKS=0 GOTOOLCHAIN=local
  export RUSTUP_AUTO_INSTALL=0 RUSTUP_SKIP_UPDATE_CHECK=1
  export DOTNET_SKIP_FIRST_TIME_EXPERIENCE=1 DOTNET_CLI_TELEMETRY_OPTOUT=1 DOTNET_NOLOGO=1
  builtin print -rn -- $'\0BACUMI_PID_'"$_bacumi_developer_probe_token=$sysparams[pid]"$'\0'
  "${_bacumi_developer_probe_argv[@]}" </dev/null 2>/dev/null
  builtin print -rn -- $'\0BACUMI_EXIT_'"$_bacumi_developer_probe_token=$?"$'\0'
}

# Every probe gets an isolated terminal/process group, never the user's input.
# A shared deadline bounds the full prompt's Git + runtime probes. All group
# members are terminated after success or failure, even if a tool leaves a child.
_bacumi_developer_probe() {
  emulate -L zsh
  local -i limit=$1 descriptor=-1 worker=0 created=0 finished=0 code=124 read_code ticks
  shift
  local -a _bacumi_developer_probe_argv=("$@")
  local _bacumi_developer_probe_token="${RANDOM}_${RANDOM}_${RANDOM}_${RANDOM}_$EPOCHREALTIME"
  local pid_marker=$'\0BACUMI_PID_'"$_bacumi_developer_probe_token=" exit_marker=$'\0BACUMI_EXIT_'"$_bacumi_developer_probe_token="
  local name="_bacumi_probe_$sysparams[pid]" data='' chunk='' suffix='' prefix='' REPLY
  local -F remaining deadline=${_bacumi_developer_probe_deadline:-$(( EPOCHREALTIME + 0.18 ))}
  typeset -g _bacumi_developer_probe_output=''
  (( deadline > EPOCHREALTIME )) || return 124
  {
    if builtin zpty -b "$name" _bacumi_developer_probe_worker; then
      created=1; descriptor=$REPLY
      while (( (remaining = deadline - EPOCHREALTIME) > 0 )); do
        chunk=''
        builtin zpty -r -t "$name" chunk
        read_code=$?
        (( read_code == 0 )) && data+=$chunk
        if (( worker == 0 )) && [[ $data == "$pid_marker"*$'\0'* ]]; then
          prefix=${data#"$pid_marker"}
          prefix=${prefix%%$'\0'*}
          if [[ $prefix == <-> ]] && (( prefix > 1 )); then worker=$prefix
          else break
          fi
          data=${data#"$pid_marker$prefix"$'\0'}
        fi
        (( ${#data} <= limit + 128 )) || break
        suffix=${data##*"$exit_marker"}
        if [[ $suffix == <->$'\0' ]]; then
          code=${suffix%$'\0'}
          data=${data%"$exit_marker"*}
          (( ${#data} <= limit )) && finished=1
          break
        fi
        (( read_code == 2 )) && break
        if (( read_code != 0 )); then
          ticks=$(( remaining*100 )); (( ticks < 1 )) && ticks=1
          builtin zselect -r $descriptor -t $ticks >/dev/null 2>&1
        fi
      done
    fi
  } always {
    (( worker > 1 )) && builtin kill -KILL -- -$worker 2>/dev/null
    (( created )) && builtin zpty -d "$name" 2>/dev/null
  }
  (( finished )) || return 124
  # PTY output converts LF to CRLF; metadata and Git records use NUL framing.
  (( code == 0 )) && _bacumi_developer_probe_output=${data//$'\r\n'/$'\n'}
  return $code
}

