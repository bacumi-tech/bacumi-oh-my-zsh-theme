#!/bin/sh
# Install only Bacumi-owned files. Never edit .zshrc or download executable code.
set -eu
custom_dir=${ZSH_CUSTOM:-${ZSH:-$HOME/.oh-my-zsh}/custom}
action=install
while [ "$#" -gt 0 ]; do
  case "$1" in
    --custom-dir) [ "$#" -ge 2 ] || { echo '--custom-dir needs a path' >&2; exit 2; }; custom_dir=$2; shift 2 ;;
    --uninstall) action=uninstall; shift ;;
    --check-config) action=check; shift ;;
    --help) echo 'Usage: sh install.sh [--custom-dir PATH] [--uninstall | --check-config]'; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; exit 2 ;;
  esac
done
[ -n "$custom_dir" ] || { echo 'Custom directory must not be empty' >&2; exit 2; }
source_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
destination=$custom_dir/themes/bacumi
marker=$destination/.bacumi-installed
fail() { echo "$1" >&2; exit 1; }
check_config() {
  config=${ZDOTDIR:-$HOME}/.zshrc
  if [ ! -r "$config" ]; then
    printf 'No readable Zsh configuration at %s.\n' "$config"
    return 0
  fi
  if awk '/^[[:space:]]*#/ { next } /source[[:space:]].*(p10k-instant-prompt|\.p10k\.zsh|powerlevel10k.*zsh-theme)/ { found=1 } END { exit !found }' "$config"; then
    printf 'Powerlevel10k initialization detected in %s.\n' "$config"
    echo 'Disable its instant-prompt block and .p10k.zsh source before using Bacumi.'
    echo 'The git and extract plugins can stay enabled.'
    return 1
  fi
  echo 'No active Powerlevel10k initialization detected.'
}
if [ "$action" = check ]; then check_config; exit $?; fi
old_files='bacumi-dark.zsh-theme bacumi-light.zsh-theme lib/prompt.zsh'
files="$old_files bacumi-developer-dark.zsh-theme bacumi-developer-light.zsh-theme lib/developer-prompt.zsh"
legacy_files=$files
files="$files lib/probe.zsh"
owned_files=$files
manifest() {
  echo 'bacumi-oh-my-zsh-theme v1'
  for file in $1; do
    [ -f "$destination/$file" ] && [ ! -L "$destination/$file" ] || return 1
    printf '%s ' "$file"
    cksum < "$destination/$file"
  done
}

[ ! -L "$destination" ] || fail "Refusing linked installation: $destination"
if [ -e "$destination" ]; then
  [ -f "$marker" ] && [ ! -L "$marker" ] || fail "Folder is not owned by this installer: $destination"
  [ ! -L "$destination/lib" ] || fail 'Refusing linked library directory'
  expected=$(cat "$marker")
  # Historical v1 receipts own three files; verify that exact set before migration.
  if actual=$(manifest "$files") && [ "$actual" = "$expected" ]; then
    owned_files=$files
  elif actual=$(manifest "$legacy_files") && [ "$actual" = "$expected" ]; then
    owned_files=$legacy_files
    [ ! -e "$destination/lib/probe.zsh" ] && [ ! -L "$destination/lib/probe.zsh" ] || fail "Unowned file would be replaced: lib/probe.zsh"
  elif actual=$(manifest "$old_files") && [ "$actual" = "$expected" ]; then
    owned_files=$old_files
    if [ "$action" = install ]; then
      for file in bacumi-developer-dark.zsh-theme bacumi-developer-light.zsh-theme lib/developer-prompt.zsh lib/probe.zsh; do
        [ ! -e "$destination/$file" ] && [ ! -L "$destination/$file" ] || fail "Unowned file would be replaced: $file"
      done
    fi
  else
    fail 'Bacumi files were modified locally. Back up or move the installation before replacing it.'
  fi
elif [ "$action" = uninstall ]; then
  echo 'Bacumi is already uninstalled.'
  exit 0
fi

if [ "$action" = uninstall ]; then
  for file in $owned_files; do rm -- "$destination/$file"; done
  rm -- "$marker"
  rmdir -- "$destination/lib" 2>/dev/null || :
  rmdir -- "$destination" 2>/dev/null || :
  echo 'Bacumi removed. Restore your previous ZSH_THEME in .zshrc before opening a new shell.'
else
  # Validate the complete source before writing any installed file.
  for file in $files; do [ -f "$source_dir/$file" ] || fail "Missing release file: $file"; done
  stage=$(mktemp -d "${TMPDIR:-/tmp}/bacumi-theme.XXXXXXXX")
  transaction=0
  cleanup() {
    status=$?
    trap - EXIT HUP INT TERM
    set +e
    rollback_failed=0
    if [ "$status" -ne 0 ] && [ "$transaction" -eq 1 ]; then
      for file in $files .bacumi-installed; do
        if [ -f "$stage/backup/$file" ]; then
          cp -p -- "$stage/backup/$file" "$destination/$file" || rollback_failed=1
        else
          rm -f -- "$destination/$file" || rollback_failed=1
        fi
      done
    fi
    if [ "$rollback_failed" -eq 1 ]; then
      echo "Rollback failed; recovery copies retained in $stage/backup" >&2
    else
      rm -rf -- "$stage"
    fi
    exit "$status"
  }
  trap cleanup EXIT
  trap 'exit 130' HUP INT TERM
  mkdir -p -- "$stage/payload/lib" "$stage/backup/lib"
  for file in $files; do cp -- "$source_dir/$file" "$stage/payload/$file"; done
  for file in $owned_files .bacumi-installed; do
    [ ! -f "$destination/$file" ] || cp -p -- "$destination/$file" "$stage/backup/$file"
  done
  mkdir -p -- "$destination/lib"
  transaction=1
  for file in $files; do cp -- "$stage/payload/$file" "$destination/$file"; done
  manifest "$files" > "$marker"
  transaction=0
  printf 'Installed Developer and Lightweight themes into %s\n' "$destination"
  echo ''
  echo 'Choose one Developer theme in ~/.zshrc (recommended):'
  echo '  ZSH_THEME="bacumi/bacumi-developer-dark"'
  echo '  ZSH_THEME="bacumi/bacumi-developer-light"'
  echo ''
  echo 'Optional Lightweight themes (minimal prompt):'
  echo '  ZSH_THEME="bacumi/bacumi-dark"'
  echo '  ZSH_THEME="bacumi/bacumi-light"'
  echo ''
  echo 'Keep only one ZSH_THEME assignment, before Oh My Zsh is sourced.'
  echo 'Open a new terminal window to apply it.'
  check_config || :
fi
