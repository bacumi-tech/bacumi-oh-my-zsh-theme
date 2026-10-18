<div align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/icons/icon-dark-128.png">
    <img src="assets/icons/icon-light-128.png" width="96" height="96" alt="Bacumi for Oh My Zsh">
  </picture>
  <h1>Bacumi for Oh My Zsh</h1>
  <p>A focused shell prompt, in Dark and Light.</p>
  <p>
    <a href="https://github.com/bacumi-tech/bacumi-oh-my-zsh-theme/releases/tag/v0.1.1">Download 0.1.1 preview</a> ·
    <a href="#installation">Installation</a> ·
    <a href="BRAND.md">Brand and icons</a> ·
    <a href="LICENSE">MIT license</a>
  </p>
</div>

Bacumi puts your directory, Git state and last command result in one compact
prompt. Warm accents and coordinated Dark/Light variants bring the Bacumi palette
to your shell, with a standard-font design.

**Preview release.** Automated prompt and installer checks run on macOS and Linux.
WSL-specific visual review remains pending; see [validation](VALIDATION.md).

## Preview

<table>
  <tr><th>Bacumi Dark</th><th>Bacumi Light</th></tr>
  <tr>
    <td width="50%"><img src="assets/bacumi-dark.svg" width="400" alt="Illustrated Bacumi Dark shell prompt"></td>
    <td width="50%"><img src="assets/bacumi-light.svg" width="400" alt="Illustrated Bacumi Light shell prompt"></td>
  </tr>
</table>

Illustrated prompt previews, not native terminal screenshots.

| Indicator | Meaning |
| --- | --- |
| Directory | Current path, shortened to fit the window |
| `git:main` | Current Git branch |
| `*` | Staged, unstaged or untracked changes |
| `git:@abc1234` | Detached HEAD, identified by commit prefix |
| `!1` | The previous command exited with status 1 |

## Installation

### Requirements

- macOS, Linux or WSL with **Zsh 5.8+** and **Oh My Zsh** already installed.
- **Git 2.20+** for Git indicators; the prompt works without Git.

Installation from ZIP requires no Git, special font or package manager.

### 1. Download and extract

Download [bacumi-oh-my-zsh-theme-0.1.1.zip](https://github.com/bacumi-tech/bacumi-oh-my-zsh-theme/releases/download/v0.1.1/bacumi-oh-my-zsh-theme-0.1.1.zip)
from the [GitHub release](https://github.com/bacumi-tech/bacumi-oh-my-zsh-theme/releases/tag/v0.1.1).
Extract the ZIP and open a terminal in the folder containing `install.sh`.

To verify the ZIP first, download `SHA256SUMS` from the same release into the ZIP's
folder and run:

```sh
shasum -a 256 -c SHA256SUMS
```

On Linux, you can use `sha256sum -c SHA256SUMS` instead.

### 2. Install both appearances

```sh
sh install.sh
```

The default destination is `~/.oh-my-zsh/custom/themes/bacumi`. The script also
respects exported `ZSH_CUSTOM` and `ZSH` locations. For a custom directory that is
configured only inside `.zshrc`, pass its actual path:

```sh
sh install.sh --custom-dir '/path/to/oh-my-zsh/custom'
```

The installer copies only Bacumi theme files. You choose the active theme in
your configuration; `.zshrc` is preserved.

### 3. Select Dark or Light

Back up your configuration before editing it:

```sh
cp -n ~/.zshrc ~/.zshrc.before-bacumi
```

In `~/.zshrc`, replace the current `ZSH_THEME` assignment with one of these
**before** the line that sources Oh My Zsh:

```zsh
ZSH_THEME="bacumi/bacumi-dark"
```

For a light terminal background, use:

```zsh
ZSH_THEME="bacumi/bacumi-light"
```

Open a new terminal window. In a Git repository, the prompt should display your
branch. Run `false` to check that `!1` appears in the next prompt.

**Switching from Powerlevel10k:** disable its instant-prompt block and any line
that sources `.p10k.zsh` in your `.zshrc` while trying Bacumi. Keep your old
configuration so you can switch back. Use one prompt theme at a time.

### Install from a Git checkout

```sh
git clone https://github.com/bacumi-tech/bacumi-oh-my-zsh-theme.git
cd bacumi-oh-my-zsh-theme
sh install.sh
```

Then select the theme as above. The installed files are independent of the
checkout; after `git pull`, rerun `sh install.sh` to update them.

## Customize

Place optional settings in `.zshrc` before Oh My Zsh is sourced:

```zsh
BACUMI_COLOR_MODE=auto  # Detect truecolor; otherwise use ANSI colors
# BACUMI_COLOR_MODE=truecolor
# BACUMI_COLOR_MODE=ansi
# BACUMI_COLOR_MODE=none
# BACUMI_SHOW_GIT=0     # Disable Git checks in large repositories
```

`TERM=dumb` always uses plain text. ANSI mode follows your terminal's palette;
truecolor mode uses the exact Bacumi prompt colors. Choose the appearance that
matches your terminal background; the prompt does not change that background.
A window at least 40 columns wide is recommended.

The theme sets the left prompt, clears the right prompt and registers one
`precmd` hook. For coordinated output under WSL, pair it with
[Bacumi for Windows Terminal](https://github.com/bacumi-tech/bacumi-windows-terminal-theme).

## Update and uninstall

**Update:** run the installer from a newer release, or pull your Git checkout
and rerun the installer. Installed files with local edits are protected; back
up or move your custom copy before replacing it. Use a separate theme directory
for personal modifications.

**Uninstall:** restore your previous `ZSH_THEME` in `.zshrc`, then run this from
an extracted release or source checkout:

```sh
sh install.sh --uninstall
```

Pass the same `--custom-dir` if you used one. Removal preserves unrelated themes.
Open a new shell afterward.

## Brand and artwork

Both terminal projects use Bacumi Brand v1.0's approved editor palette. Original
[Dark/Light product icons](assets/icons/) are supplied as SVG masters and
transparent PNGs from 16 to 1024 px, with [provenance](assets/icons/provenance.json).
They are available for documentation, listings and shortcuts; the installer
leaves your terminal application's icon as configured.

Read [BRAND.md](BRAND.md) for color roles, icon rationale and reproduction details.

## Development

<details>
<summary>Build, verify and contribute</summary>

Use a source checkout with Python 3.10+, Zsh 5.8+ and Git 2.28+ for the test
fixtures. Standard checks use no third-party Python packages or private repositories.

```sh
python3 scripts/build.py --check
python3 scripts/build-icons.py --check
python3 scripts/check-brand.py
sh -n install.sh
zsh -n bacumi-dark.zsh-theme bacumi-light.zsh-theme lib/prompt.zsh
python3 -m unittest discover -s tests -v
python3 scripts/package.py
```

Set `BACUMI_OMZ_DIR` to a real Oh My Zsh checkout to also run framework-loading
tests; CI supplies a pinned checkout on macOS and Linux.

Edit `palette.json`, then run `python3 scripts/build.py` to regenerate entry
points and illustrated previews. Brand changes require review of both appearances.
Regenerate icon SVGs with `python3 scripts/build-icons.py`; optional PNG export
uses `python3 scripts/export-icons.py` with PyMuPDF in the contributor environment.
Committed PNGs require no renderer to use or verify.

See the [validation record](VALIDATION.md), [changelog](CHANGELOG.md) and
[contribution guide](CONTRIBUTING.md).

</details>

## Support and license

[Open an issue](https://github.com/bacumi-tech/bacumi-oh-my-zsh-theme/issues)
with your operating system, Zsh/Oh My Zsh versions, selected appearance and a
non-sensitive example.

Themes, palette, code, documentation and original product icons are covered by
the [MIT License](LICENSE). Bacumi names identify this project; trademark rights
and endorsement of forks are not granted. The theme makes no runtime network
requests and collects no telemetry.

Built using [Oh My Zsh's custom theme mechanism](https://github.com/ohmyzsh/ohmyzsh/wiki/Customization)
and [Zsh prompt expansion](https://zsh.sourceforge.io/Doc/Release/Prompt-Expansion.html).
