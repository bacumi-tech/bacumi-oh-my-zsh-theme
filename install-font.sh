#!/bin/sh
# Optional per-user MesloLGS NF installation. No font binaries are bundled.
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
manifest=$root/fonts/meslolgs-nf.tsv
source_dir=
uninstall=0
custom=0
case $(uname -s) in
 Darwin) destination=$HOME/Library/Fonts ;;
 Linux) destination=${XDG_DATA_HOME:-$HOME/.local/share}/fonts ;;
 *) echo 'Use Install-Font.ps1 on the Windows host for Windows Terminal.' >&2; exit 1 ;;
esac
fail() { echo "Font installation: $*" >&2; exit 1; }
while [ "$#" -gt 0 ]; do
 case $1 in
  --font-dir|--source-dir|--manifest)
   [ "$#" -ge 2 ] || fail "Missing value for $1"
   case $1 in --font-dir) destination=$2; custom=1;; --source-dir) source_dir=$2;; --manifest) manifest=$2;; esac
   shift 2 ;;
  --uninstall) uninstall=1; shift ;;
  --help) echo 'Usage: sh install-font.sh [--uninstall] [--font-dir PATH] [--source-dir PATH] [--manifest PATH]'; exit 0 ;;
  *) fail "Unknown option: $1" ;;
 esac
done
[ -n "$destination" ] || fail 'Empty font directory'
[ ! -L "$destination" ] || fail 'Linked font directory is not supported'
receipt=$destination/.bacumi-meslolgs-nf.receipt
notes=Bacumi-MesloLGS-NF
tab=$(printf '\t')
allowed() {
 case $1 in
  'MesloLGS NF Regular.ttf'|'MesloLGS NF Bold.ttf'|'MesloLGS NF Italic.ttf'|'MesloLGS NF Bold Italic.ttf'|Bacumi-MesloLGS-NF/LICENSE-MesloLGS-NF.txt|Bacumi-MesloLGS-NF/Apache-2.0.txt|Bacumi-MesloLGS-NF/NOTICE.txt) return 0 ;;
  *) return 1 ;;
 esac
}
sha() {
 if command -v shasum >/dev/null 2>&1; then shasum -a 256 "$1" | cut -d ' ' -f 1
 elif command -v sha256sum >/dev/null 2>&1; then sha256sum "$1" | cut -d ' ' -f 1
 else fail 'A SHA-256 utility (shasum or sha256sum) is required'; fi
}
[ ! -L "$destination/$notes" ] || fail 'Linked notice directory'
stage=$(mktemp -d "${TMPDIR:-/tmp}/bacumi-font.XXXXXXXX")
transaction=0
had_destination=0; had_notes=0
[ ! -d "$destination" ] || had_destination=1
[ ! -d "$destination/$notes" ] || had_notes=1
cleanup() {
 status=$?
 trap - EXIT HUP INT TERM
 set +e
 rollback_failed=0
 if [ "$status" -ne 0 ] && [ "$transaction" -eq 1 ]; then
  while IFS="$tab" read -r state name; do
   if [ "$state" = present ]; then
    cp -p -- "$stage/backup/$name" "$destination/$name" || rollback_failed=1
   else
    rm -f -- "$destination/$name" || rollback_failed=1
   fi
  done < "$stage/backup-index"
  if [ "$had_notes" -eq 0 ]; then rmdir "$destination/$notes" 2>/dev/null || :; fi
  if [ "$had_destination" -eq 0 ]; then rmdir "$destination" 2>/dev/null || :; fi
 fi
 if [ "$rollback_failed" -eq 1 ]; then
  echo "Font rollback failed; recovery copies retained in $stage/backup" >&2
 else
  rm -rf -- "$stage"
 fi
 exit "$status"
}
trap cleanup EXIT
trap 'exit 130' HUP INT TERM
begin_transaction() {
 mkdir -p "$stage/backup/$notes"
 : > "$stage/backup-index"
 while IFS= read -r name; do
  if [ -e "$destination/$name" ]; then
   cp -p -- "$destination/$name" "$stage/backup/$name"
   printf 'present\t%s\n' "$name" >> "$stage/backup-index"
  else
   printf 'absent\t%s\n' "$name" >> "$stage/backup-index"
  fi
 done < "$stage/changes"
 transaction=1
}
: > "$stage/owned"
if [ -e "$receipt" ] || [ -L "$receipt" ]; then
 [ -f "$receipt" ] && [ ! -L "$receipt" ] || fail 'Invalid ownership receipt'
 [ "$(head -n 1 "$receipt")" = 'bacumi-meslolgs-nf v1' ] || fail 'Unrecognized ownership receipt'
 tail -n +2 "$receipt" > "$stage/owned"
 while IFS="$tab" read -r digest name extra; do
  allowed "$name" || fail 'Invalid owned filename'
  [ -z "${extra:-}" ] || fail 'Invalid ownership receipt'
  [ ! -L "$destination/$name" ] && [ -f "$destination/$name" ] || fail "Owned font/notice is missing or linked: $name"
  [ "$(sha "$destination/$name")" = "$digest" ] || fail "Preserving modified file: $name"
 done < "$stage/owned"
fi
if [ "$uninstall" -eq 1 ]; then
 [ -f "$receipt" ] || fail 'No Bacumi font ownership receipt; no fonts were removed'
 cut -f 2 "$stage/owned" > "$stage/changes"
 printf '%s\n' '.bacumi-meslolgs-nf.receipt' >> "$stage/changes"
 begin_transaction
 while IFS="$tab" read -r digest name; do rm -- "$destination/$name"; done < "$stage/owned"
 rm -- "$receipt"
 rmdir "$destination/$notes" 2>/dev/null || :
 rmdir "$destination" 2>/dev/null || :
 transaction=0
 echo 'Removed only verified Bacumi-installed fonts and notices.'
else
 [ -f "$manifest" ] || fail 'Missing font manifest'
 : > "$stage/expected"
 while IFS="$tab" read -r digest name url extra; do
  case $name in 'MesloLGS NF Regular.ttf'|'MesloLGS NF Bold.ttf'|'MesloLGS NF Italic.ttf'|'MesloLGS NF Bold Italic.ttf') :;; *) fail 'Unexpected font filename';; esac
  [ -z "${extra:-}" ] && [ "${#digest}" -eq 64 ] || fail 'Invalid manifest record'
  case $digest in *[!0-9a-f]*) fail 'Invalid SHA-256';; esac
  case $url in https://*) :;; *) fail 'Font URLs must use HTTPS';; esac
  if cut -f 2 "$stage/expected" | grep -Fx "$name" >/dev/null; then fail 'Duplicate font record'; fi
  if [ -n "$source_dir" ]; then
   [ -f "$source_dir/$name" ] || fail "Missing source: $name"
   cp -- "$source_dir/$name" "$stage/$name"
  else
   command -v curl >/dev/null 2>&1 || fail 'curl is required to download fonts'
   curl --fail --location --silent --show-error --proto '=https' --proto-redir '=https' --connect-timeout 20 --max-time 180 "$url" -o "$stage/$name" || fail "Download failed: $name"
  fi
  [ "$(sha "$stage/$name")" = "$digest" ] || fail "SHA-256 mismatch: $name"
  printf '%s\t%s\n' "$digest" "$name" >> "$stage/expected"
 done < "$manifest"
 [ "$(wc -l < "$stage/expected" | tr -d ' ')" = 4 ] || fail 'Expected four font records'
 mkdir "$stage/$notes"
 for name in LICENSE-MesloLGS-NF.txt Apache-2.0.txt NOTICE.txt; do
  cp -- "$root/fonts/$name" "$stage/$notes/$name"
  printf '%s\t%s\n' "$(sha "$stage/$notes/$name")" "$notes/$name" >> "$stage/expected"
 done
 # Check every target before making any destination changes.
 while IFS="$tab" read -r digest name; do
  [ ! -L "$destination/$name" ] || fail "Preserving linked file: $name"
  if [ -e "$destination/$name" ]; then
   [ -f "$destination/$name" ] || fail "Preserving existing path: $name"
   if ! cut -f 2 "$stage/owned" | grep -Fx "$name" >/dev/null; then
    [ "$(sha "$destination/$name")" = "$digest" ] || fail "Preserving existing file: $name"
   fi
  fi
 done < "$stage/expected"
 : > "$stage/changes"
 printf '%s\n' 'bacumi-meslolgs-nf v1' > "$stage/receipt"
 while IFS="$tab" read -r digest name; do
  if [ ! -e "$destination/$name" ] || cut -f 2 "$stage/owned" | grep -Fx "$name" >/dev/null; then
   printf '%s\n' "$name" >> "$stage/changes"
   printf '%s\t%s\n' "$digest" "$name" >> "$stage/receipt"
  fi
 done < "$stage/expected"
 printf '%s\n' '.bacumi-meslolgs-nf.receipt' >> "$stage/changes"
 begin_transaction
 mkdir -p -- "$destination/$notes"
 while IFS= read -r name; do
  [ "$name" != '.bacumi-meslolgs-nf.receipt' ] || continue
  cp -- "$stage/$name" "$destination/$name"
 done < "$stage/changes"
 mv -- "$stage/receipt" "$receipt"
 transaction=0
 echo 'MesloLGS NF installed. Select the MesloLGS NF family in your terminal font settings.'
 echo 'Apple Terminal: Settings > Profiles > Font. iTerm2: Settings > Profiles > Text > Font.'
 echo 'Enable prompt icons only after selecting the font (BACUMI_PROMPT_ICONS=1).'
fi
if [ "$custom" -eq 0 ] && [ "$(uname -s)" = Linux ] && command -v fc-cache >/dev/null 2>&1; then
 fc-cache -f "$destination" || echo 'Font cache refresh failed; reopen the terminal or refresh it manually.' >&2
fi
