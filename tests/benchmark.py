"""Diagnostic prompt timing in a synthetic local repository; not a performance claim."""
from pathlib import Path
import os
import statistics
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix="bacumi-benchmark-") as temp:
    directory = Path(temp)
    subprocess.run(["git", "init", "-b", "main", "--quiet"], cwd=temp, check=True)
    for i in range(2500):
        (directory / f"tracked-{i}.txt").write_text("fixture\n")
    subprocess.run(["git", "add", "."], cwd=temp, check=True)
    subprocess.run(["git", "-c", "user.name=Theme Test", "-c", "user.email=test@example.invalid", "commit", "--quiet", "-m", "fixture"], cwd=temp, check=True)
    for i in range(2500):
        (directory / f"untracked-{i}.txt").write_text("fixture\n")
    script = '''source "$THEME_FILE"
zmodload zsh/datetime
typeset -F started
for iteration in {1..20}; do
  started=$EPOCHREALTIME
  true
  _bacumi_precmd
  print -r -- $(( (EPOCHREALTIME - started) * 1000 ))
done
'''
    env = {**os.environ, "THEME_FILE": str(ROOT / "bacumi-dark.zsh-theme"), "TERM": "xterm-256color"}
    result = subprocess.run(["zsh", "-dfc", script], cwd=temp, env=env, check=True, text=True, capture_output=True)
    timings = [float(line) for line in result.stdout.splitlines()]
    print(f"2500 tracked + 2500 untracked files, 20 prompts: median {statistics.median(timings):.1f} ms; max {max(timings):.1f} ms. Local filesystem only.")
