# Changelog

## 0.3.2 — 2026-10-18 (preview)

- Add readable failure summaries beside developer prompt exit codes in Dark/Light.
- Let compact failure prompts use two lines when needed to retain Git state and
  the explanation; clear the summary after success without changing shell status.

## 0.3.1 — 2026-10-18 (preview)

- Prevent native probes from inheriting terminal session-save and shell exit hooks.
  Their output could corrupt the framed Git result and leave `status:?` visible.
- Keep all exit hooks intact in the parent interactive shell.
- Add real-Git controlling-terminal coverage in Dark/Light and regressions for
  direct exit functions, hook arrays and EXIT traps.

## 0.3.0 — 2026-10-18 (preview)

- Add original Bacumi padded segments in Dark/Light with readable ANSI fallback.
- Bound native Git/runtime probes, close their input, cap output and clean up
  their child processes. Keep known Git HEAD visible with `status:?` when full
  status is unavailable; omit incomplete counts. Retry failed runtime probes soon.
- Add controlling-terminal and adversarial-process regressions, 40/80/120-column
  fixture matrices and previews captured from the actual native renderer.
- Fix version-file reads that waited for input from the controlling terminal.
- Add read-only Powerlevel10k initialization diagnostics and plugin migration checks.
- Publish as a preview while native terminal visual/font acceptance remains pending.

## 0.2.1 — consistent installation guidance

- Recommend Developer Dark/Light consistently in the installer and README.
- Label the original themes as optional Lightweight alternatives, with complete
  copyable assignments and an explicit instruction to keep one selection before
  Oh My Zsh loads. Theme names and runtime behavior are unchanged.

## 0.2.0 — native developer prompt preview

- Add native developer prompts with Bacumi Dark and Light, detailed Git state,
  relevant runtime versions, command failures, duration and session context.
- Offer compact layouts, width adaptation, plain text and optional font icons.
- Preserve existing theme installations and provide independent safe installers.
- Add optional MesloLGS NF download/install with pinned SHA-256 checks and retained
  upstream Apache 2.0 notices; font binaries are not bundled.
- Expand installation guidance, semantic fixtures, native tests and diagnostics.
- Remain a preview pending native Terminal/WSL visual acceptance.

## 0.1.1 — 2026-10-18 (preview)

- Verify both variants against the Bacumi Brand v1.0 editor adaptation.
- Add original Dark/Light product icons as SVG and PNG, covered by MIT.
- Include icon assets, brand documentation and provenance in the release ZIP.
- Add CI checks for approved palette colors and icon export integrity.

## 0.1.0 — 2026-10-18 (preview)

- Add coordinated Bacumi Dark and Light variants under the MIT license.
- Add native installation, update and uninstall with local-edit protection.
- Include illustrated previews, standalone validation and GitHub CI.
- Distribute an installable ZIP and SHA-256 checksum through GitHub Releases.

See VALIDATION.md for platform checks and remaining native visual review.
