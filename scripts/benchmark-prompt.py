#!/usr/bin/env python3
"""Measure native developer prompt cold shells and warm renders; no network calls."""
import argparse
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]


def git(directory, *args):
    subprocess.run(["git", "-c", "user.name=Benchmark", "-c", "user.email=benchmark@example.invalid", *args], cwd=directory, check=True, capture_output=True)


def measure(directory, samples):
    context = {**os.environ, "THEME_FILE": str(ROOT / "bacumi-developer-dark.zsh-theme"), "TERM": "xterm-256color", "NO_COLOR": "1", "BACUMI_SHOW_RUNTIMES": "0"}
    render = 'true; _bacumi_developer_precmd; print -rP -- "$PROMPT" >/dev/null'
    cold = []
    for _ in range(samples):
        start = time.perf_counter()
        subprocess.run(["zsh", "-dfc", 'source "$THEME_FILE"; COLUMNS=80; ' + render], cwd=directory, env=context, check=True, capture_output=True)
        cold.append((time.perf_counter() - start) * 1000)
    script = 'source "$THEME_FILE"; COLUMNS=80; ' + render + '; repeat ' + str(samples) + '; do start=$EPOCHREALTIME; ' + render + '; print $(( (EPOCHREALTIME-start)*1000 )); done'
    result = subprocess.run(["zsh", "-dfc", script], cwd=directory, env=context, check=True, capture_output=True, text=True)
    warm = [float(line) for line in result.stdout.splitlines()]
    return {"cold_shell_and_first_prompt_ms": {"median": round(statistics.median(cold), 3), "max": round(max(cold), 3)},
            "warm_prompt_ms": {"median": round(statistics.median(warm), 3), "max": round(max(warm), 3)}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=int, default=30)
    parser.add_argument("--large-files", type=int, default=5000)
    args = parser.parse_args()
    if args.samples < 1 or args.large_files < 1:
        parser.error("sample and file counts must be positive")
    with tempfile.TemporaryDirectory(prefix="bacumi-benchmark-") as temporary:
        parent = Path(temporary)
        directories = {name: parent / name for name in ("non_git", "clean_git", "large_git")}
        for directory in directories.values():
            directory.mkdir()
        for name in ("clean_git", "large_git"):
            directory = directories[name]
            git(directory, "init", "-b", "main")
            count = args.large_files if name == "large_git" else 1
            for index in range(count):
                (directory / f"file-{index}.txt").write_text("tracked\n")
            git(directory, "add", ".")
            git(directory, "commit", "-m", "benchmark")
            if name == "large_git":
                for index in range(max(1, count // 5)):
                    (directory / f"new-{index}.txt").write_text("untracked\n")
        output = {"environment": {"platform": platform.platform(), "machine": platform.machine(), "cpu_count": os.cpu_count(),
                                    "zsh": subprocess.check_output(["zsh", "--version"], text=True).strip(), "samples": args.samples,
                                    "large_tracked_files": args.large_files, "large_untracked_files": max(1, args.large_files // 5),
                                    "notes": "Local temporary filesystem; runtime probes disabled; no network. Cold includes shell startup. This is not native GUI visual validation."},
                  "cases": {name: measure(directory, args.samples) for name, directory in directories.items()}}
        print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
