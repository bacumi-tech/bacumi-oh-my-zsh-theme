# Bacumi for Oh My Zsh

![Bacumi Oh My Zsh Dark icon](assets/icons/icon-dark-128.png) ![Bacumi Light icon](assets/icons/icon-light-128.png)

A compact prompt in **Dark** and **Light**, with warm focus accents, readable
Git state and no required special font. Free and open source under the
[MIT License](LICENSE).

![Bacumi Dark illustrated prompt](assets/bacumi-dark.svg)
![Bacumi Light illustrated prompt](assets/bacumi-light.svg)

These are illustrated prompt previews, not terminal screenshots. The prompt
shows your directory, Git branch, `*` for staged/unstaged/untracked changes,
`@` plus the commit prefix when detached, and `!N` after a failed command.

## Install from GitHub Releases

Requires **Zsh 5.8+** and an existing **Oh My Zsh** installation on macOS,
Linux or WSL. Git is optional for installation from ZIP; Git status is shown
only if Git is available. No Node.js, Python or package manager is needed.

1. Download `bacumi-oh-my-zsh-theme-0.1.1.zip` from
   [Releases](https://github.com/bacumi-tech/bacumi-oh-my-zsh-theme/releases),
   extract it, and open a terminal in the extracted directory.
2. Install both variants:

   ```sh
   sh install.sh
   ```

3. Edit your existing `~/.zshrc`, **before** the line that sources Oh My Zsh:

   ```zsh
   ZSH_THEME="bacumi/bacumi-dark"
   ```

   Or use `ZSH_THEME="bacumi/bacumi-light"` for Light. Replace the previous
   `ZSH_THEME` assignment, then open a new shell.

The script copies only Bacumi files into
`${ZSH_CUSTOM:-${ZSH:-$HOME/.oh-my-zsh}/custom}/themes/bacumi`.
It never edits `.zshrc`, installs Oh My Zsh, changes your terminal palette, or
downloads anything. Pass `--custom-dir '/path/to/custom'` if your custom directory
is configured inside `.zshrc` and is not exported into the installer environment.

### Install using Git instead

Clone anywhere convenient and run the same installer:

```sh
git clone https://github.com/bacumi-tech/bacumi-oh-my-zsh-theme.git
cd bacumi-oh-my-zsh-theme
sh install.sh
```

The installed copy is independent of your checkout. To update it, run `git pull`
in that checkout followed by `sh install.sh` again.

## Appearance and options

Select Dark for dark terminal backgrounds and Light for light backgrounds.
The theme sets the prompt, clears the right prompt and adds one `precmd` hook.
It leaves your fonts, terminal output colors, keybindings and plugins alone.

Place optional settings before Oh My Zsh is sourced:

```zsh
BACUMI_COLOR_MODE=auto  # default: truecolor when advertised, ANSI otherwise
# BACUMI_COLOR_MODE=truecolor  # force exact Bacumi colors
# BACUMI_COLOR_MODE=ansi       # use your terminal's standard color slots
# BACUMI_COLOR_MODE=none       # plain text
# BACUMI_SHOW_GIT=0            # disable Git checks in very large repositories
```

`TERM=dumb` always uses plain text. ANSI fallback uses the terminal's own palette,
so its Dark/Light colors depend on your emulator. Pair it with
[Bacumi for Windows Terminal](https://github.com/bacumi-tech/bacumi-windows-terminal-theme)
for coordinated output under WSL. Changing a Zsh theme does not change the
terminal background. The prompt adapts path and branch lengths to window width;
40 columns or wider is recommended.

## Update and uninstall

Run the installer from a newer release to update its files. Locally edited
installed files are protected: the installer stops rather than overwriting or
deleting them. Back them up or move the `themes/bacumi` directory before replacing
them. Keep custom theme work in a separately named directory.

Restore your previous `ZSH_THEME` in `.zshrc`, then run:

```sh
sh install.sh --uninstall
```

Use the same `--custom-dir` if you installed with one. Uninstall removes only
installer-owned files and preserves unrelated themes. Open a new shell afterward.

## Development

In a source checkout, tests require Python 3.10+, Zsh 5.8+ and Git,
without third-party packages:

```sh
python3 scripts/build.py --check
sh -n install.sh
zsh -n bacumi-dark.zsh-theme bacumi-light.zsh-theme lib/prompt.zsh
python3 -m unittest discover -s tests -v
```

Edit `palette.json`, then run `python3 scripts/build.py` to regenerate the two
entry points and illustrated previews. `lib/prompt.zsh` contains the shared prompt.
Palette revision `bacumi-terminal-1` is included locally, so a standalone clone
never needs a private sibling repository. See [validation](VALIDATION.md) and
[contribution guidance](CONTRIBUTING.md).

The MIT license covers this repository's themes, palette, code, documentation
and illustrations. Bacumi names identify this project; the license does not
grant trademark rights or imply endorsement of forks. Original product icons are MIT licensed; company logo masters and
fonts are not bundled. No telemetry or runtime network calls.

Installation follows [Oh My Zsh's custom theme mechanism](https://github.com/ohmyzsh/ohmyzsh/wiki/Customization).
Prompt formatting follows [Zsh prompt expansion](https://zsh.sourceforge.io/Doc/Release/Prompt-Expansion.html).

## Bacumi brand and product icons

The palette was checked against Bacumi Brand v1.0 and its approved editor
adaptation: Graphite-derived Dark, Off-White Light, warm focus accents and
contrast-adjusted semantic colors. Both terminal-theme projects use the same
palette revision. [BRAND.md](BRAND.md) records the role mapping and icon rationale.

`assets/icons/` contains original Dark/Light SVG masters and transparent PNG
exports at 16, 32, 128, 256, 512 and 1024 px. These are product identifiers;
selecting the theme does not replace your terminal application's icon.

Contributor checks (Python standard library only):

```sh
python3 scripts/build-icons.py --check
python3 scripts/check-brand.py
```

After artwork edits, regenerate SVGs with `python3 scripts/build-icons.py`.
Refreshing PNGs uses `python3 scripts/export-icons.py`, with optional PyMuPDF
available in the contributor's environment. It is never needed by users or CI.
