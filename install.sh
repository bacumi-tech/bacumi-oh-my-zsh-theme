#!/bin/sh
# Install only Bacumi-owned files. Never edit .zshrc or download executable code.
set -eu
custom_dir=${ZSH_CUSTOM:-${ZSH:-$HOME/.oh-my-zsh}/custom}
action=install
while [ "$#" -gt 0 ]; do
  case "$1" in
    --custom-dir) [ "$#" -ge 2 ] || { echo '--custom-dir needs a path' >&2; exit 2; }; custom_dir=$2; shift 2 ;;
    --uninstall) action=uninstall; shift ;;
    --help) echo 'Usage: sh install.sh [--custom-dir PATH] [--uninstall]'; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; exit 2 ;;
  esac
done
[ -n "$custom_dir" ] || { echo 'Custom directory must not be empty' >&2; exit 2; }
source_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
destination=$custom_dir/themes/bacumi
marker=$destination/.bacumi-installed
fail() { echo "$1" >&2; exit 1; }
files='bacumi-dark.zsh-theme bacumi-light.zsh-theme lib/prompt.zsh'
manifest() {
  echo 'bacumi-oh-my-zsh-theme v1'
  for file in $files; do
    printf '%s ' "$file"
    cksum < "$destination/$file"
  done
}

[ ! -L "$destination" ] || fail "Refusing linked installation: $destination"
if [ -e "$destination" ]; then
  [ -f "$marker" ] && [ ! -L "$marker" ] || fail "Folder is not owned by this installer: $destination"
  [ ! -L "$destination/lib" ] || fail 'Refusing linked library directory'
  for file in $files; do
    [ -f "$destination/$file" ] && [ ! -L "$destination/$file" ] || fail "Missing or linked file: $file"
  done
  actual=$(manifest)
  expected=$(cat "$marker")
  [ "$actual" = "$expected" ] || fail 'Bacumi files were modified locally. Back up or move the installation before replacing it.'
elif [ "$action" = uninstall ]; then
  echo 'Bacumi is already uninstalled.'
  exit 0
fi

if [ "$action" = uninstall ]; then
  for file in $files; do rm -- "$destination/$file"; done
  rm -- "$marker"
  rmdir -- "$destination/lib" 2>/dev/null || :
  rmdir -- "$destination" 2>/dev/null || :
  echo 'Bacumi removed. Restore your previous ZSH_THEME in .zshrc before opening a new shell.'
else
  # Validate the complete source before writing any installed file.
  for file in $files; do [ -f "$source_dir/$file" ] || fail "Missing release file: $file"; done
  mkdir -p -- "$destination/lib"
  for file in $files; do cp -- "$source_dir/$file" "$destination/$file"; done
  manifest > "$marker"
  printf 'Installed Dark and Light into %s\n' "$destination"
  echo 'Set ZSH_THEME="bacumi/bacumi-dark" or "bacumi/bacumi-light" in .zshrc, then open a new shell.'
fi
