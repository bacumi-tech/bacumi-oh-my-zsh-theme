"""Exercise real Zsh prompt expansion and Git state in disposable directories."""
from pathlib import Path
import os
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
ESCAPE = re.compile(r"\x1b\[[0-9;]*[mK]")


def run_zsh(script, cwd, mode="dark", env=None):
    context = {**os.environ, "TERM": "xterm-256color", "COLORTERM": "truecolor", "THEME_FILE": str(ROOT / f"bacumi-{mode}.zsh-theme"), **(env or {})}
    result = subprocess.run(["zsh", "-dfc", 'source "$THEME_FILE" || exit; ' + script], cwd=cwd, env=context, text=True, capture_output=True)
    if result.returncode:
        raise AssertionError(f"Zsh failed ({result.returncode}): {result.stderr}")
    return result.stdout


class Prompt(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="bacumi-test-")
        self.addCleanup(self.temp.cleanup)
        self.cwd = Path(self.temp.name)

    def git(self, *args):
        return subprocess.check_output(["git", *args], cwd=self.cwd, text=True, stderr=subprocess.DEVNULL).strip()

    def init_git(self):
        self.git("init", "-b", "main")
        self.git("-c", "user.name=Theme Test", "-c", "user.email=test@example.invalid", "commit", "--allow-empty", "-m", "fixture")

    def rendered(self, command="true", mode="dark", env=None):
        return ESCAPE.sub("", run_zsh(f'{command}; _bacumi_precmd; print -rP -- "$PROMPT"', self.cwd, mode, env)).strip()

    def test_non_git_and_previous_failure(self):
        for mode in ("dark", "light"):
            self.assertTrue(self.rendered(mode=mode).endswith(">"))
            self.assertNotIn("git:", self.rendered(mode=mode))
            self.assertIn("!7", self.rendered("(exit 7)", mode))
            self.assertNotIn("!0", self.rendered(mode=mode))

    def test_clean_dirty_untracked_and_detached_git(self):
        self.init_git()
        self.assertIn("git:main", self.rendered())
        self.assertNotIn("*", self.rendered())
        tracked = self.cwd / "tracked.txt"
        tracked.write_text("original")
        self.git("add", ".")
        self.assertIn("*", self.rendered())
        self.git("-c", "user.name=Theme Test", "-c", "user.email=test@example.invalid", "commit", "-m", "track")
        tracked.write_text("changed")
        self.assertIn("*", self.rendered())
        self.git("restore", "tracked.txt")
        (self.cwd / "new.txt").write_text("new")
        self.assertIn("*", self.rendered())
        self.git("checkout", "--detach", "HEAD")
        self.assertIn("git:@" + self.git("rev-parse", "--short=7", "HEAD"), self.rendered())

    def test_unborn_branch(self):
        self.git("init", "-b", "new-project")
        self.assertIn("git:new-project", self.rendered())

    def test_variants_truecolor_and_ansi_fallback(self):
        dark = run_zsh('true; _bacumi_precmd; print -rP -- "$PROMPT"', self.cwd)
        light = run_zsh('true; _bacumi_precmd; print -rP -- "$PROMPT"', self.cwd, "light")
        self.assertNotEqual(dark, light)
        self.assertIn("38;2;255;179;71", dark)
        self.assertIn("38;2;163;65;0", light)
        ansi = run_zsh('true; _bacumi_precmd; print -rP -- "$PROMPT"', self.cwd, env={"COLORTERM": "", "BACUMI_COLOR_MODE": "ansi"})
        self.assertNotIn("38;2;", ansi)
        dumb = run_zsh('true; _bacumi_precmd; print -rP -- "$PROMPT"', self.cwd, env={"TERM": "dumb", "COLORTERM": ""})
        self.assertNotIn("\x1b", dumb)

    def test_literal_directory_and_branch_do_not_execute_or_expand(self):
        strange = self.cwd / 'spațiu %F{red} $(touch PWNED) `touch OWNED` !'
        strange.mkdir()
        output = ESCAPE.sub("", run_zsh('COLUMNS=240; true; _bacumi_precmd; print -rP -- "$PROMPT"', strange))
        self.assertIn("%F{red}", output)
        self.assertIn("$(touch PWNED)", output)
        self.assertIn("`touch OWNED`", output)
        self.assertFalse((strange / "PWNED").exists())
        self.assertFalse((strange / "OWNED").exists())
        self.init_git()
        self.git("checkout", "-b", "feat/%F{red}$(id)")
        output = ESCAPE.sub("", run_zsh('COLUMNS=240; true; _bacumi_precmd; print -rP -- "$PROMPT"', self.cwd))
        self.assertIn("feat/%F{red}$(id)", output)

    def test_controls_are_not_emitted_from_directory(self):
        strange = self.cwd / "line\n\x1b[31m"
        strange.mkdir()
        output = ESCAPE.sub("", run_zsh('true; _bacumi_precmd; print -rP -- "$PROMPT"', strange)).rstrip("\n")
        self.assertNotIn("\n", output)
        self.assertNotIn("\x1b", output)

    def test_promptbang_preserves_literal_names_and_failure_marker(self):
        directory = self.cwd / "work!"
        directory.mkdir()
        output = ESCAPE.sub("", run_zsh('setopt promptbang; COLUMNS=240; false; _bacumi_precmd; print -rP -- "$PROMPT"', directory))
        self.assertIn("work!", output)
        self.assertIn(" !1 ", output)

    def test_narrow_terminal_and_repeated_load(self):
        self.init_git()
        self.git("checkout", "-b", "feature/this-is-a-very-long-branch-name")
        output = ESCAPE.sub("", run_zsh('COLUMNS=40; source "$THEME_FILE"; true; _bacumi_precmd; print -rP -- "$PROMPT"; print -r -- ${(M)#precmd_functions:#_bacumi_precmd}', self.cwd)).splitlines()
        self.assertLessEqual(len(output[0]), 39)
        self.assertEqual(output[1], "1")

    def test_real_interactive_prompt_preserves_last_command_status(self):
        import pty
        import select
        import time
        master, slave = pty.openpty()
        env = {**os.environ, "TERM": "xterm-256color", "COLORTERM": "truecolor", "THEME_FILE": str(ROOT / "bacumi-dark.zsh-theme")}
        shell = subprocess.Popen(["zsh", "-dfi"], cwd=self.cwd, env=env, stdin=slave, stdout=slave, stderr=slave)
        os.close(slave)
        try:
            os.write(master, b'source "$THEME_FILE"\nfalse\nprint -r -- "saved-exit=$?"\nexit\n')
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
                elif shell.poll() is not None:
                    break
            shell.wait(timeout=3)
            decoded = ESCAPE.sub("", output.decode(errors="replace"))
            self.assertIn("!1", decoded)
            self.assertIn("saved-exit=1", decoded)
        finally:
            if shell.poll() is None:
                shell.kill()
                shell.wait()
            os.close(master)


class Installer(unittest.TestCase):
    def test_install_update_and_uninstall_preserve_configuration(self):
        with tempfile.TemporaryDirectory(prefix="bacumi-install-") as temp:
            custom = Path(temp) / "custom with spaces"
            custom.mkdir()
            unrelated = custom / "themes/existing.zsh-theme"
            unrelated.parent.mkdir()
            unrelated.write_text("keep this")
            install = ["sh", str(ROOT / "install.sh"), "--custom-dir", str(custom)]
            subprocess.run(install, check=True, capture_output=True)
            subprocess.run(install, check=True, capture_output=True)
            theme = custom / "themes/bacumi/bacumi-light.zsh-theme"
            self.assertTrue(theme.is_file())
            env = {**os.environ, "THEME_FILE": str(theme)}
            loaded = subprocess.run(["zsh", "-dfc", 'source "$THEME_FILE"; true; _bacumi_precmd; print -rP -- "$PROMPT"'], cwd=temp, env=env, capture_output=True, text=True)
            self.assertEqual(loaded.returncode, 0, loaded.stderr)
            self.assertIn(">", loaded.stdout)
            subprocess.run(install + ["--uninstall"], check=True, capture_output=True)
            self.assertFalse(theme.exists())
            self.assertEqual(unrelated.read_text(), "keep this")

    def test_refuses_unowned_folder_and_modified_theme(self):
        with tempfile.TemporaryDirectory(prefix="bacumi-install-") as temp:
            custom = Path(temp)
            target = custom / "themes/bacumi"
            target.mkdir(parents=True)
            sentinel = target / "personal.txt"
            sentinel.write_text("keep")
            command = ["sh", str(ROOT / "install.sh"), "--custom-dir", str(custom)]
            self.assertNotEqual(subprocess.run(command, capture_output=True).returncode, 0)
            self.assertEqual(sentinel.read_text(), "keep")
            sentinel.unlink()
            target.rmdir()
            subprocess.run(command, check=True, capture_output=True)
            theme = target / "bacumi-dark.zsh-theme"
            theme.write_text("local edit")
            for suffix in ([], ["--uninstall"]):
                self.assertNotEqual(subprocess.run(command + suffix, capture_output=True).returncode, 0)
                self.assertEqual(theme.read_text(), "local edit")

    @unittest.skipUnless(os.environ.get("BACUMI_OMZ_DIR"), "Set BACUMI_OMZ_DIR to check a real Oh My Zsh checkout")
    def test_loads_both_variants_through_real_oh_my_zsh(self):
        with tempfile.TemporaryDirectory(prefix="bacumi-omz-") as temp:
            custom = Path(temp) / "custom"
            subprocess.run(["sh", str(ROOT / "install.sh"), "--custom-dir", str(custom)], check=True, capture_output=True)
            for mode in ("dark", "light"):
                env = {**os.environ, "ZSH": os.environ["BACUMI_OMZ_DIR"], "ZSH_CUSTOM": str(custom),
                       "ZSH_CACHE_DIR": str(Path(temp) / "cache"), "ZSH_COMPDUMP": str(Path(temp) / "compdump"),
                       "ZSH_THEME": f"bacumi/bacumi-{mode}", "TERM": "xterm-256color"}
                result = subprocess.run(["zsh", "-dfc", 'zstyle ":omz:update" mode disabled; plugins=(); source "$ZSH/oh-my-zsh.sh"; (( $+functions[_bacumi_precmd] )) || exit 1; false; _bacumi_precmd; print -rP -- "$PROMPT"'], env=env, cwd=temp, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("!1", result.stdout)


if __name__ == "__main__":
    unittest.main()
