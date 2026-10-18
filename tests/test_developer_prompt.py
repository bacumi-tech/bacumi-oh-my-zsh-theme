"""Native developer prompt contract, using real Zsh and disposable Git repositories."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
ANSI = re.compile(r"\x1b\[[0-9;]*[mK]")


def shell(script, cwd, mode="dark", env=None, raw=False):
    context = {**os.environ, "TERM": "xterm-256color", "COLORTERM": "truecolor", "NO_COLOR": "",
               "THEME_FILE": str(ROOT / f"bacumi-developer-{mode}.zsh-theme"), **(env or {})}
    result = subprocess.run([shutil.which("zsh"), "-dfc", 'source "$THEME_FILE" || exit; ' + script],
                            cwd=cwd, env=context, text=True, capture_output=True)
    if result.returncode:
        raise AssertionError(result.stderr)
    return result.stdout if raw else ANSI.sub("", result.stdout)


class DeveloperPrompt(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="bacumi-dev-")
        self.addCleanup(self.temp.cleanup)
        self.cwd = Path(self.temp.name)

    def git(self, *args):
        return subprocess.check_output(["git", "-c", "user.name=Prompt Test", "-c", "user.email=test@example.invalid", *args], cwd=self.cwd, text=True, stderr=subprocess.DEVNULL).strip()

    def init(self):
        self.git("init", "-b", "main")
        (self.cwd / "tracked").write_text("base\n")
        self.git("add", ".")
        self.git("commit", "-m", "base")

    def render(self, command="true", extra="", env=None):
        return shell(f'{extra}; {command}; _bacumi_developer_precmd; print -rP -- "$PROMPT"', self.cwd, env=env)

    def test_shared_semantic_fixtures(self):
        for fixture in json.loads((ROOT / "tests/fixtures/git-cases.json").read_text()):
            with self.subTest(fixture=fixture["name"]):
                output = shell('_bacumi_developer_parse_git "$FIXTURE"; for k in branch unborn detached staged unstaged untracked conflicts ahead behind; do print -r -- "$k=${_bacumi_developer_git[$k]}"; done', self.cwd, env={"FIXTURE": fixture["porcelain"]})
                actual = dict(line.split("=", 1) for line in output.splitlines())
                expected = fixture["expected"]
                if expected is None:
                    self.assertEqual(actual["branch"], "")
                else:
                    for key, value in expected.items():
                        self.assertEqual(actual[key], "" if value is None else str(int(value)) if isinstance(value, bool) else str(value))

    def test_real_git_counts_detached_unborn_and_upstream(self):
        self.init()
        self.assertIn("git:main", self.render())
        (self.cwd / "tracked").write_text("staged\n")
        self.git("add", ".")
        (self.cwd / "tracked").write_text("unstaged\n")
        (self.cwd / "new\nfile").write_text("untracked")
        output = self.render(extra="COLUMNS=160")
        for label in ("+1", "~1", "?1"):
            self.assertIn(label, output)
        self.git("branch", "origin-main")
        self.git("branch", "--set-upstream-to=origin-main")
        self.git("commit", "-m", "ahead")
        self.assertIn("ahead:1", self.render(extra="COLUMNS=160"))
        self.git("checkout", "--detach", "HEAD")
        self.assertIn("git:@" + self.git("rev-parse", "--short=7", "HEAD"), self.render())

    def test_width_result_duration_and_hook_idempotence(self):
        self.init()
        self.git("checkout", "-b", "feature/very-long-branch-name-that-needs-shortening")
        for width in (40, 80):
            output = self.render("(exit 7)", f"COLUMNS={width}; _bacumi_developer_started=$(( EPOCHREALTIME - 3.2 ))")
            self.assertEqual(len(output.rstrip("\n").splitlines()), 2)
            self.assertTrue(all(len(line) <= width for line in output.splitlines()))
            self.assertIn("!7", output)
        output = shell('source "$THEME_FILE"; print -r -- ${(M)#precmd_functions:#_bacumi_developer_precmd} ${(M)#preexec_functions:#_bacumi_developer_preexec}; BACUMI_PROMPT_LAYOUT=compact; COLUMNS=40; false; _bacumi_developer_precmd; print -rP -- "$PROMPT"', self.cwd)
        self.assertEqual(output.splitlines()[0], "1 1")
        self.assertEqual(len(output.splitlines()), 2)
        self.assertIn("!1", output)
        self.assertIn("3.2s", self.render(extra="COLUMNS=160; _bacumi_developer_started=$(( EPOCHREALTIME - 3.2 ))"))

    def test_literal_data_and_colors_icons(self):
        strange = self.cwd / 'spațiu %F{red} $(touch PWNED) `touch OWNED` !\n\x1b\u202e'
        strange.mkdir()
        output = shell('COLUMNS=240; setopt promptbang; false; _bacumi_developer_precmd; print -rP -- "$PROMPT"', strange, env={"BACUMI_COLOR_MODE": "none"})
        for literal in ("%F{red}", "$(touch PWNED)", "`touch OWNED`", "!1"):
            self.assertIn(literal, output)
        self.assertNotIn("\x1b", output)
        self.assertNotIn("\u202e", output)
        self.assertEqual(len(output.rstrip("\n").splitlines()), 2)
        self.assertFalse((strange / "PWNED").exists())
        self.assertFalse((strange / "OWNED").exists())
        self.assertIn(">", self.render())
        self.assertIn("❯", self.render(env={"BACUMI_PROMPT_ICONS": "1"}))
        self.assertNotEqual(shell('true; _bacumi_developer_precmd; print -rP -- "$PROMPT"', self.cwd, raw=True), shell('true; _bacumi_developer_precmd; print -rP -- "$PROMPT"', self.cwd, "light", raw=True))

    def test_switching_lightweight_and_developer_preserves_one_git_probe(self):
        tools = self.cwd / "bin"
        tools.mkdir()
        counter = self.cwd / "calls"
        fake = tools / "git"
        fake.write_text('#!/bin/sh\nprintf "call\\n" >> "$CALLS"\nprintf "# branch.oid abcdef123\\0# branch.head main\\0"\n')
        fake.chmod(0o755)
        output = shell('''for iteration in 1 2; do
          source "$LIGHTWEIGHT_FILE"; for hook in "${precmd_functions[@]}"; do true; "$hook"; done
          print -r -- "light:${(M)#precmd_functions:#_bacumi_precmd}:${(M)#precmd_functions:#_bacumi_developer_precmd}:${(M)#preexec_functions:#_bacumi_developer_preexec}"
          source "$THEME_FILE"; for hook in "${precmd_functions[@]}"; do true; "$hook"; done
          print -r -- "developer:${(M)#precmd_functions:#_bacumi_developer_precmd}:${(M)#precmd_functions:#_bacumi_precmd}:${(M)#preexec_functions:#_bacumi_developer_preexec}"
        done''', self.cwd, env={"PATH": str(tools) + ":" + os.environ["PATH"], "CALLS": str(counter), "LIGHTWEIGHT_FILE": str(ROOT / "bacumi-dark.zsh-theme")})
        self.assertEqual(output.splitlines(), ["light:1:0:0", "developer:1:0:1"] * 2)
        self.assertEqual(len(counter.read_text().splitlines()), 4)

    def test_color_fallback_and_no_color(self):
        for mode in ("dark", "light"):
            truecolor = shell('true; _bacumi_developer_precmd; print -rP -- "$PROMPT"', self.cwd, mode, raw=True)
            self.assertIn("38;2;", truecolor)
        ansi = shell('true; _bacumi_developer_precmd; print -rP -- "$PROMPT"', self.cwd, env={"BACUMI_COLOR_MODE": "ansi"}, raw=True)
        self.assertIn("\x1b[", ansi)
        self.assertNotIn("38;2;", ansi)
        for settings in ({"NO_COLOR": "1"}, {"TERM": "dumb"}, {"BACUMI_COLOR_MODE": "none"}):
            self.assertNotIn("\x1b", shell('true; _bacumi_developer_precmd; print -rP -- "$PROMPT"', self.cwd, env=settings, raw=True))

    def test_git_toggles_and_one_process_per_prompt(self):
        tools = self.cwd / "bin"
        tools.mkdir()
        counter = self.cwd / "calls"
        fake = tools / "git"
        fake.write_text('#!/bin/sh\nprintf "call\\n" >> "$CALLS"\nprintf "# branch.oid abcdef123\\0# branch.head main\\0? new\\0"\n')
        fake.chmod(0o755)
        env = {"PATH": str(tools) + ":" + os.environ["PATH"], "CALLS": str(counter)}
        shell('true; _bacumi_developer_precmd; print -rP -- "$PROMPT"; print -rP -- "$PROMPT"', self.cwd, env=env)
        self.assertEqual(counter.read_text().splitlines(), ["call"])
        shell('BACUMI_SHOW_GIT=0; true; _bacumi_developer_precmd', self.cwd, env=env)
        self.assertEqual(counter.read_text().splitlines(), ["call"])
        output = shell('BACUMI_GIT_DETAILS=0; true; _bacumi_developer_precmd; print -rP -- "$PROMPT"', self.cwd, env=env)
        self.assertIn("git:main", output)
        self.assertNotIn("?1", output)

    def test_runtime_relevance_cache_environment_and_version_file_invalidation(self):
        tools = self.cwd / "bin"
        tools.mkdir()
        counter = self.cwd / "versions"
        node = tools / "node"
        node.write_text('#!/bin/sh\nprintf "probe\\n" >> "$VERSIONS"\nprintf "v22.1.0\\n"\n')
        node.chmod(0o755)
        env = {"PATH": str(tools) + ":" + os.environ["PATH"], "VERSIONS": str(counter)}
        self.assertNotIn("node:", self.render(env=env))
        (self.cwd / "package.json").write_text("{}")
        output = shell('COLUMNS=200; true; _bacumi_developer_precmd; print -rP -- "$PROMPT"; true; _bacumi_developer_precmd; print -rP -- "$PROMPT"; print v22 > .node-version; true; _bacumi_developer_precmd', self.cwd, env=env)
        self.assertIn("node:22.1.0", output)
        self.assertEqual(counter.read_text().splitlines(), ["probe", "probe"])
        output = self.render(extra="COLUMNS=200", env={**env, "VIRTUAL_ENV": "/tmp/env %F{red}"})
        self.assertIn("venv:env %F{red}", output)

    def test_operations_worktree_and_conflicts_take_priority(self):
        self.init()
        gitdir = self.cwd / ".git"
        (gitdir / "MERGE_HEAD").write_text("fixture")
        self.assertIn("merge", self.render())
        (gitdir / "MERGE_HEAD").unlink()
        (gitdir / "rebase-merge").mkdir()
        self.assertIn("rebase", self.render())
        (gitdir / "rebase-merge").rmdir()
        self.git("checkout", "-b", "other")
        (self.cwd / "tracked").write_text("other\n")
        self.git("commit", "-am", "other")
        self.git("checkout", "main")
        (self.cwd / "tracked").write_text("main\n")
        self.git("commit", "-am", "main")
        subprocess.run(["git", "merge", "other"], cwd=self.cwd, capture_output=True)
        output = self.render("false", "COLUMNS=40")
        self.assertIn("conflict:1", output)
        self.assertIn("!1", output)
        self.assertTrue(all(len(line) <= 40 for line in output.splitlines()))

    def test_installer_migrates_old_three_file_receipt_without_overwriting_unowned_files(self):
        target = self.cwd / "themes/bacumi"
        (target / "lib").mkdir(parents=True)
        old = ["bacumi-dark.zsh-theme", "bacumi-light.zsh-theme", "lib/prompt.zsh"]
        receipt = "bacumi-oh-my-zsh-theme v1\n"
        for name in old:
            (target / name).write_bytes((ROOT / name).read_bytes())
            checksum = subprocess.check_output(["cksum"], input=(target / name).read_bytes()).decode().strip()
            receipt += f"{name} {checksum}\n"
        (target / ".bacumi-installed").write_text(receipt)
        command = ["sh", str(ROOT / "install.sh"), "--custom-dir", str(self.cwd)]
        subprocess.run(command, check=True, capture_output=True)
        self.assertTrue((target / "lib/developer-prompt.zsh").is_file())
        subprocess.run(command + ["--uninstall"], check=True, capture_output=True)
        self.assertFalse(target.exists())


    def test_git_rename_newlines_worktree_and_behind(self):
        self.init()
        self.git("mv", "tracked", "renamed\nname")
        output = self.render(extra="COLUMNS=160")
        self.assertIn("+1", output)
        self.assertNotIn("~1", output)
        self.git("commit", "-m", "rename")
        self.git("branch", "upstream")
        self.git("branch", "--set-upstream-to=upstream")
        self.git("checkout", "upstream")
        self.git("commit", "--allow-empty", "-m", "ahead on upstream")
        self.git("checkout", "main")
        self.assertIn("behind:1", self.render(extra="COLUMNS=160"))
        worktree = self.cwd / "linked"
        self.git("worktree", "add", "-b", "linked", str(worktree))
        gitfile = (worktree / ".git").read_text().strip().removeprefix("gitdir: ")
        (Path(gitfile) / "rebase-apply").mkdir()
        output = shell('true; _bacumi_developer_precmd; print -rP -- "$PROMPT"', worktree)
        self.assertIn("rebase", output)

    def test_hook_coexistence_status_jobs_and_ssh_context(self):
        output = shell('other_hook() { print hook-ran; }; precmd_functions+=(other_hook); source "$THEME_FILE"; false; _bacumi_developer_precmd; other_hook; print -r -- "hooks=${(j:,:)precmd_functions}"; print -rP -- "$PROMPT"; COLUMNS=240; sleep 5 &; true; _bacumi_developer_precmd; print -rP -- "$PROMPT"; kill $!; wait $! 2>/dev/null; true', self.cwd, env={"SSH_CONNECTION": "fixture"})
        self.assertIn("hook-ran", output)
        self.assertIn("hooks=_bacumi_developer_precmd,other_hook", output)
        self.assertIn("!1", output)
        self.assertIn("jobs:1", output)
        self.assertIn("@", output)

    def test_real_interactive_shell_preserves_status_and_directory(self):
        import pty
        import select
        import time
        master, slave = pty.openpty()
        env = {**os.environ, "TERM": "dumb", "THEME_FILE": str(ROOT / "bacumi-developer-dark.zsh-theme")}
        process = subprocess.Popen(["zsh", "-dfi"], cwd=self.cwd, env=env, stdin=slave, stdout=slave, stderr=slave)
        os.close(slave)
        try:
            os.write(master, b'source "$THEME_FILE"\nfalse\nprint -r -- "saved-exit=$? cwd=$PWD"\nexit\n')
            output = b""
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                if select.select([master], [], [], .1)[0]:
                    try:
                        chunk = os.read(master, 65536)
                    except OSError:
                        break
                    if not chunk:
                        break
                    output += chunk
                elif process.poll() is not None:
                    break
            process.wait(timeout=3)
            decoded = output.decode(errors="replace")
            self.assertIn("!1", decoded)
            self.assertIn(f"saved-exit=1 cwd={self.cwd.resolve()}", decoded)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
            os.close(master)

    def test_all_relevant_runtimes_and_missing_executables(self):
        tools = self.cwd / "bin"
        tools.mkdir()
        for name, output in (("node", "v22.1.0"), ("python3", "Python 3.13.0"), ("go", "go version go1.23.2 darwin/arm64"), ("rustc", "rustc 1.82.0 (fixture)"), ("dotnet", "8.0.100")):
            tool = tools / name
            tool.write_text("#!/bin/sh\nprintf '%s\\n' '" + output + "'\n")
            tool.chmod(0o755)
        for name in ("package.json", "pyproject.toml", "go.mod", "Cargo.toml", "app.csproj"):
            (self.cwd / name).touch()
        output = self.render(extra="COLUMNS=240", env={"PATH": str(tools)})
        for label in ("node:22.1.0", "python:3.13.0", "go:1.23.2", "rust:1.82.0", "dotnet:8.0.100"):
            self.assertIn(label, output)
        for tool in tools.iterdir():
            tool.unlink()
        output = self.render(extra="COLUMNS=240", env={"PATH": str(tools)})
        self.assertNotIn("node:", output)
        self.assertNotIn("git:", output)

    def test_old_receipt_migration_rejects_collision_and_modified_files(self):
        target = self.cwd / "themes/bacumi"
        (target / "lib").mkdir(parents=True)
        receipt = "bacumi-oh-my-zsh-theme v1\n"
        for name in ("bacumi-dark.zsh-theme", "bacumi-light.zsh-theme", "lib/prompt.zsh"):
            (target / name).write_bytes((ROOT / name).read_bytes())
            checksum = subprocess.check_output(["cksum"], input=(target / name).read_bytes()).decode().strip()
            receipt += f"{name} {checksum}\n"
        (target / ".bacumi-installed").write_text(receipt)
        collision = target / "bacumi-developer-dark.zsh-theme"
        collision.write_text("personal")
        command = ["sh", str(ROOT / "install.sh"), "--custom-dir", str(self.cwd)]
        self.assertNotEqual(subprocess.run(command, capture_output=True).returncode, 0)
        self.assertEqual(collision.read_text(), "personal")
        collision.unlink()
        owned = target / "bacumi-dark.zsh-theme"
        owned.write_text("modified")
        self.assertNotEqual(subprocess.run(command, capture_output=True).returncode, 0)
        self.assertEqual(owned.read_text(), "modified")

    @unittest.skipUnless(os.environ.get("BACUMI_OMZ_DIR"), "Set BACUMI_OMZ_DIR for real Oh My Zsh integration")
    def test_real_oh_my_zsh_developer_variants(self):
        custom = self.cwd / "custom"
        subprocess.run(["sh", str(ROOT / "install.sh"), "--custom-dir", str(custom)], check=True, capture_output=True)
        for mode in ("dark", "light"):
            env = {**os.environ, "ZSH": os.environ["BACUMI_OMZ_DIR"], "ZSH_CUSTOM": str(custom), "ZSH_CACHE_DIR": str(self.cwd / "cache"), "ZSH_COMPDUMP": str(self.cwd / "compdump"), "ZSH_THEME": f"bacumi/bacumi-developer-{mode}", "TERM": "xterm-256color"}
            result = subprocess.run(["zsh", "-dfc", 'zstyle ":omz:update" mode disabled; plugins=(); source "$ZSH/oh-my-zsh.sh"; false; _bacumi_developer_precmd; print -rP -- "$PROMPT"'], cwd=self.cwd, env=env, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("!1", result.stdout)


if __name__ == "__main__":
    unittest.main()
