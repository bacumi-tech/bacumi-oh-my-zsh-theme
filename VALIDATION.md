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

## Brand review — 0.1.1

Both Dark/Light palettes match the approved Bacumi editor adaptation exactly,
including all 16 ANSI colors. Master icon colors are the six exact Bacumi Brand
v1.0 values. The icons use original product-specific geometry, with no company
mark, third-party product logo, font or embedded image. Flat Graphite is the
approved small-format treatment; Light uses Off-White and Beige with contrast
edges. SVGs and PNGs were visually inspected at 256 px and in a small-size sheet.

CI validates the approved palette snapshot, exact master colors, generated SVG
consistency, PNG dimensions and source/export hashes. The brand checks require
only Python's standard library. Artwork export is an optional contributor step.
The existing native Windows Terminal/WSL visual-review limits still apply.

## Native developer prompt — 0.2.0 preview

Local Zsh 5.9 checks passed on macOS 27.0.1 ARM64, including real Oh My Zsh
loading and interactive failure/PWD preservation. The developer suite covers
shared Git semantic fixtures; real counts, rename paths with newlines, detached
and unborn branches, local ahead/behind, conflicts, merge/rebase/worktrees;
hook coexistence, jobs/SSH; runtime relevance/cache invalidation; 40-column
priorities; plain/ANSI/truecolor/icons and NO_COLOR; old receipt migration and
unowned-file collisions. The original lightweight suite remains in place.

Optional font tests use controlled local downloads and temporary directories.
They cover checksum/partial-source failures before mutation, updates, repeat
installation, third-party matching/conflicting fonts, local edits, linked paths,
and separate ownership/uninstall. The four actual pinned upstream faces were
also checked against the committed hashes in a temporary Mac font directory.
No normal user font directory or shell configuration was changed.

`python3 scripts/check-package.py` extracts the actual ZIP, installs into a
temporary custom path, loads the installed developer prompt and uninstalls.
Font binaries are explicitly forbidden in the archive.

### Performance sample

`python3 scripts/benchmark-prompt.py` separates cold shell startup + first prompt
from warm rendering. This macOS sample used Zsh 5.9, 10 logical CPUs, 30 samples,
local temporary storage and no runtime probes; large = 5,000 tracked files and
1,000 untracked files. Medians (milliseconds):

| Case | Cold shell + first prompt | Warm prompt |
| --- | ---: | ---: |
| Non-Git | 20.206 | 7.249 |
| Clean Git | 23.362 | 9.416 |
| Large Git | 38.661 | 26.147 |

The largest observed warm large-repository render was 103.169 ms. These are
diagnostic observations, not an instant-prompt performance promise. CI prints
new macOS/Linux measurements; WSL/network filesystem performance is unverified.
Use `BACUMI_GIT_DETAILS=0` to omit detailed scanning or `BACUMI_SHOW_GIT=0` to
skip Git. Runtime probes are cached with a bounded expiry. Native macOS Terminal,
iTerm2 and WSL visual/font review remains a separate manual acceptance step.

## 0.3.0 preview — 2026-10-18

The original automated suite missed a controlling-terminal bug: Zsh `read -k`
read from `/dev/tty` despite file redirection. The regression now uses
`pty.fork()` (not only openpty/Popen), actual installed themes and real Oh My Zsh.
Small version files, empty/non-newline files, typed commands after `cd`, plugin
loading, status, resizing, Unicode/multiline input and Ctrl-C are exercised.

Native external probes now share an approximately 180 ms subprocess budget per
prompt, with EOF input, bounded output, timeout cleanup and short failure caching.
A Git status failure keeps bounded local HEAD information with explicit `status:?`;
partial/stale counts are suppressed. The budget does not bound filesystem or OS
scheduling calls. Deliberately daemonizing executable wrappers are outside the
ordinary-runtime fixtures; no arbitrary-process containment guarantee is made.

Real renderer fixtures cover Dark/Light, developer/compact, 40/80/120 columns,
plain/ANSI/truecolor and icons, including conflict/failure/unknown-state priority.
Developer SVGs now rerender from the actual native formatting code on controlled
data; they remain distinct from native emulator screenshots. ANSI fallback uses
readable inverse colors against the terminal's current background. Exact Bacumi
RGB colors require truecolor support.

Local macOS checks passed for native Zsh and PowerShell 7.6.7, including the
existing installer/font suites and archive installation. Hosted macOS/Linux and
Windows PowerShell 5.1/7 checks also passed:

- [Zsh macOS/Linux validation](https://github.com/bacumi-tech/bacumi-oh-my-zsh-theme/actions/runs/39140787999)
- [Windows PowerShell 5.1/7 validation](https://github.com/bacumi-tech/bacumi-windows-terminal-theme/actions/runs/39140424302)

Native Apple Terminal/iTerm2/Windows Terminal visual acceptance remains manual.
Version 0.3.0 remains a preview pending that acceptance.

Zsh additionally isolates each probe in a native private process group/terminal,
uses nonce-framed output, and tests successful/hung probe child cleanup, terminal
input isolation, output overflow, cleanup function interception, malformed HEAD,
raw C1 byte filtering without damaging Unicode and read-only detection of legacy
Powerlevel10k initialization. Local total: 53 unittest tests, including a
288-render fixture matrix and six controlling-terminal integration tests.

A separate read-only cycle through the user's reported .NET project used the
actual installed tools, isolated startup configuration and `git`/`extract`
plugins. Dark/Light returned after `cd` in 154/194 ms, with PWD/status and return
directory verified. No project or normal shell configuration was changed.
