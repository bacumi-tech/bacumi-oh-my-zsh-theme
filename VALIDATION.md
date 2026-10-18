# Validation and compatibility

Runtime: Zsh 5.8+ on macOS, Linux or WSL, with Oh My Zsh and Git 2.20+ for
Git indicators. Git is optional; the prompt works without it. Contributor tests
use Git 2.28+ for named-branch fixture initialization.

## Automated checks

- Real Zsh prompt expansion in both modes, including truecolor, ANSI fallback
  and plain text. An interactive pseudo-terminal verifies the failure indicator
  and preservation of the last command's exit status.
- Clean/staged/unstaged/untracked Git state, unborn branches and detached HEAD.
- Spaces, Unicode, percent escapes, shell-looking path/branch names and control
  characters. Display data is escaped and never passed to `eval`.
- Width adaptation at 40 columns and idempotent hook registration on reload.
- Installation/update/removal in temporary paths containing spaces; unrelated
  themes and local edits are preserved. Installed theme entry points load their
  shared library from the installed directory.
- Both installed variants load through a real Oh My Zsh checkout. CI pins
  upstream `964ddf789b022b6958b27d02d7fa54f552de21e9` and runs on macOS and Linux.

Local development on 18 October 2026 used macOS Zsh 5.9, Python 3.13, Git and the
real upstream framework. CI supplies a separate Linux check. WSL-specific native
visual review remains pending; Linux checks alone are not a WSL test.

## Performance and limits

The prompt runs one `git status` process before each new command prompt, without
optional Git locks or filesystem-monitor hooks. Cursor redraw performs no Git
process. Large repositories, remote filesystems and untracked trees can still
make status slow. Set `BACUMI_SHOW_GIT=0` to disable this work. Benchmark output
from `tests/benchmark.py` is diagnostic, not a performance guarantee.

The prompt sets `PROMPT`, clears `RPROMPT`, enables prompt substitution/percent
expansion and registers one hook. Other prompt engines can replace it. Terminal
backgrounds and non-prompt output are controlled by the emulator and applications.
Use truecolor mode for exact Bacumi colors; ANSI fallback follows the terminal's
palette. The illustrated SVGs are not native screenshots. The initial release
is a preview while collecting native visual feedback, including WSL.
