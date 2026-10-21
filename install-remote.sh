#!/bin/sh
# Download a versioned release, verify it, then use the local installer.
set -eu
version=0.3.4
name=bacumi-oh-my-zsh-theme-$version
base=https://github.com/bacumi-tech/bacumi-oh-my-zsh-theme/releases/download/v$version
stage=$(mktemp -d "${TMPDIR:-/tmp}/bacumi-download.XXXXXXXX")
trap 'rm -rf -- "$stage"' EXIT
trap 'exit 130' HUP INT TERM
curl --fail --silent --show-error --location "$base/$name.zip" -o "$stage/$name.zip"
curl --fail --silent --show-error --location "$base/SHA256SUMS" -o "$stage/SHA256SUMS"
(cd "$stage" && shasum -a 256 -c SHA256SUMS)
unzip -q "$stage/$name.zip" -d "$stage"
sh "$stage/$name/install.sh" "$@"
