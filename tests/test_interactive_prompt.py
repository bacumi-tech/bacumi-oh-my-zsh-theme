"""Controlling-terminal regressions for the installed theme and real Oh My Zsh.

Unlike openpty()+Popen(), pty.fork() gives Zsh a controlling terminal. That
distinction matters: Zsh's `read -k` can otherwise silently read the wrong input.
Set BACUMI_OMZ_DIR to a real, existing Oh My Zsh checkout; nothing is downloaded.
"""
import errno
import fcntl
import os
from pathlib import Path
import pty
import select
import shlex
import shutil
import signal
import struct
import subprocess
import sys
import tempfile
import termios
import time
import unittest


ROOT = Path(__file__).resolve().parents[1]
READY = b"\x1b]777;bacumi-test-ready\x07"
EXECUTING = b"\x1b]777;bacumi-test-exec\x07"
PROMPT_TIMEOUT = 2.0


class InteractiveZsh:
    """One disposable Zsh session, with bounded reads and session cleanup."""

    def __init__(self, directory, env):
        self.pending = b""
        self.transcript = b""
        self.pid, self.master = pty.fork()
        if self.pid == 0:
            try:
                os.chdir(directory)
                os.execve(shutil.which("zsh"), ["zsh", "-di"], env)
            finally:
                os._exit(127)
        self.resize(120)

    def resize(self, columns):
        fcntl.ioctl(self.master, termios.TIOCSWINSZ, struct.pack("HHHH", 30, columns, 0, 0))

    def send(self, text):
        os.write(self.master, text.encode() if isinstance(text, str) else text)

    def read_until(self, marker=READY, timeout=PROMPT_TIMEOUT):
        deadline = time.monotonic() + timeout
        while marker not in self.pending:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise AssertionError(
                    f"Interactive Zsh did not return {marker!r} within {timeout}s. "
                    f"Terminal output: {self.transcript[-8000:].decode(errors='replace')!r}")
            if not select.select([self.master], [], [], remaining)[0]:
                continue
            try:
                chunk = os.read(self.master, 65536)
            except OSError as error:
                if error.errno == errno.EIO:
                    raise AssertionError("Interactive Zsh exited before returning a prompt") from error
                raise
            if not chunk:
                raise AssertionError("Interactive Zsh closed its terminal before returning a prompt")
            self.pending += chunk
            self.transcript += chunk
        end = self.pending.index(marker) + len(marker)
        result, self.pending = self.pending[:end], self.pending[end:]
        return result.decode(errors="replace")

    def command(self, command):
        self.send(command + "\n")
        # A window change can redraw the old prompt. Synchronize with actual
        # command execution before accepting a new prompt as completion.
        self.read_until(EXECUTING)
        return self.read_until()

    def close(self):
        if self.master is None:
            return
        # Foreground commands may have a separate job-control process group.
        try:
            foreground = os.tcgetpgrp(self.master)
        except OSError:
            foreground = self.pid
        for group in {foreground, self.pid}:
            if group > 0 and group != os.getpgrp():
                try:
                    os.killpg(group, signal.SIGKILL)
                except ProcessLookupError:
                    pass
        os.close(self.master)
        self.master = None
        try:
            os.waitpid(self.pid, 0)
        except ChildProcessError:
            pass


@unittest.skipUnless(shutil.which("zsh") and os.environ.get("BACUMI_OMZ_DIR"),
                     "Set BACUMI_OMZ_DIR to run controlling-terminal Oh My Zsh tests")
class InteractivePrompt(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="bacumi-pty-")
        self.addCleanup(self.temp.cleanup)
        self.cwd = Path(self.temp.name).resolve()
        self.home = self.cwd / "home"
        self.home.mkdir()
        self.custom = self.cwd / "custom"
        subprocess.run(["sh", str(ROOT / "install.sh"), "--custom-dir", str(self.custom)],
                       check=True, capture_output=True, timeout=10)
        self.tools = self.cwd / "bin"
        self.tools.mkdir()
        # Every runtime and Git is local and deterministic. In particular rustup,
        # SDK resolvers and user tool managers cannot initiate network activity.
        fixture = """#!{python}
import os, pathlib, sys, time
name = pathlib.Path(sys.argv[0]).name
# The OMZ git plugin checks the binary version during startup. The hang
# fixture targets the theme's status probe, not framework initialization.
if name == 'git' and any(arg in ('--version', 'version') for arg in sys.argv[1:]):
    print('git version 2.50.0')
    sys.exit(0)
with open(os.environ['PROBE_LOG'], 'a') as log:
    log.write(name + ' ' + str(os.getpid()) + '\\n')
action = os.environ.get('PROBE_ACTION_' + name, '')
if action == 'read':
    sys.stdin.read()
    with open(os.environ['PROBE_LOG'], 'a') as log:
        log.write(name + ' ' + str(os.getpid()) + ' eof\\n')
elif action == 'hang':
    time.sleep(10)
elif action == 'tree':
    child = os.fork()
    if child == 0:
        with open(os.environ['PROBE_LOG'], 'a') as log:
            log.write(name + '-child ' + str(os.getpid()) + '\\n')
    time.sleep(10)
if name == 'git':
    if action:
        sys.stdout.write('# branch.oid abcdef123\\0# branch.head fixture-main\\0')
    else:
        sys.exit(128)
else:
    print({{'node': 'v22.1.0', 'python3': 'Python 3.13.0',
           'python': 'Python 3.13.0', 'go': 'go version go1.23.2 test/fixture',
           'rustc': 'rustc 1.82.0', 'dotnet': '8.0.100'}}[name])
""".format(python=sys.executable)
        for tool in ("git", "node", "python", "python3", "go", "rustc", "dotnet"):
            executable = self.tools / tool
            executable.write_text(fixture)
            executable.chmod(0o755)
        self.probe_log = self.cwd / "probes"
        self.addCleanup(self.kill_fixture_probes)
        # macOS may inspect a newly written executable on its first launch.
        # Warm only these disposable fixtures before measuring prompt behavior;
        # this does not change the theme's production probe deadline.
        warm_env = {key: value for key, value in os.environ.items()
                    if not key.startswith("PROBE_ACTION_")}
        warm_env["PROBE_LOG"] = os.devnull
        for executable in self.tools.iterdir():
            subprocess.run([str(executable), "--version"], env=warm_env,
                           stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, timeout=5)

    def kill_fixture_probes(self):
        # Also clean an incorrectly implemented timeout's detached fixture child.
        # All PIDs are recorded by our disposable executables, never discovered
        # from or applied to the user's existing shell/tool processes.
        if self.probe_log.exists():
            pids = {int(line.split()[1]) for line in self.probe_log.read_text().splitlines()}
            for pid in pids:
                try:
                    os.kill(pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass

    def start(self, mode="dark", extra_env=None):
        (self.home / ".zshrc").write_text('''
zstyle ':omz:update' mode disabled
DISABLE_AUTO_UPDATE=true
DISABLE_UPDATE_PROMPT=true
ZSH_DISABLE_COMPFIX=true
plugins=(git extract)
source "$ZSH/oh-my-zsh.sh"
(( $+functions[_bacumi_developer_precmd] )) || exit 91
PROMPT+=$'%{\\e]777;bacumi-test-ready\\a%}'
bacumi_test_preexec() { print -rn -- $'\\e]777;bacumi-test-exec\\a'; }
preexec_functions+=(bacumi_test_preexec)
''')
        # Avoid inheriting runtime managers, SSH state or prompt configuration.
        env = {key: value for key, value in os.environ.items()
               if not key.startswith(("BACUMI_", "ZSH", "PROBE_"))
               and key not in {"VIRTUAL_ENV", "CONDA_PREFIX", "PYENV_VERSION", "RUSTUP_TOOLCHAIN", "DOTNET_ROOT", "SSH_TTY", "SSH_CONNECTION"}}
        env.update({"HOME": str(self.home), "ZDOTDIR": str(self.home),
                    "ZSH": os.environ["BACUMI_OMZ_DIR"], "ZSH_CUSTOM": str(self.custom),
                    "ZSH_CACHE_DIR": str(self.cwd / "cache"), "ZSH_COMPDUMP": str(self.cwd / "compdump"),
                    "ZSH_THEME": f"bacumi/bacumi-developer-{mode}",
                    "TERM": "xterm-256color", "COLORTERM": "truecolor", "NO_COLOR": "",
                    "PATH": str(self.tools) + os.pathsep + os.defpath,
                    "PROBE_LOG": str(self.probe_log), "BACUMI_COLOR_MODE": "none",
                    "LC_ALL": "en_US.UTF-8", **(extra_env or {})})
        session = InteractiveZsh(self.cwd, env)
        self.addCleanup(session.close)
        session.read_until(timeout=10)
        return session

    def assert_pwd(self, session, directory):
        # The expected text is absent from the input echo, so this proves the
        # command ran and was not consumed by a prompt-time read from /dev/tty.
        output = session.command("printf '\\x50\\x57\\x44=%s\\n' \"$PWD\"")
        self.assertIn("PWD=" + str(directory) + "\r\n", output)

    def test_empty_enter_clears_previous_failure(self):
        session = self.start()
        self.assertIn("!1 command failed", session.command("false"))
        for blank in ("", "   ", ""):
            session.send(blank + "\n")
            self.assertNotIn("command failed", session.read_until())
        self.assertIn("!1 command failed", session.command("false"))

    def test_small_version_files_return_prompt_without_consuming_input(self):
        files = {"global.json": '{"sdk":{"version":"8.0.100"}}\n',
                 ".nvmrc": "22\n", ".node-version": "22.1.0",
                 ".python-version": "", "rust-toolchain": "stable\n",
                 "rust-toolchain.toml": '[toolchain]\nchannel="stable"\n'}
        for mode in ("dark", "light"):
            for index, (filename, content) in enumerate(files.items()):
                with self.subTest(mode=mode, version_file=filename):
                    session = self.start(mode)
                    project = self.cwd / f"{mode}-project-{index}"
                    project.mkdir()
                    (project / filename).write_text(content)
                    # No subsequent keystroke is sent until the prompt returns.
                    session.command("cd -- " + shlex.quote(str(project)))
                    self.assert_pwd(session, project)
                    session.command("cd -- " + shlex.quote(str(self.cwd)))
                    self.assert_pwd(session, self.cwd)
                    session.close()

    def test_commands_status_resize_unicode_multiline_and_interrupt(self):
        session = self.start()
        output = session.command("[[ -o interactive && -t 0 && -t 1 ]] && : < /dev/tty && printf '\\x54\\x54\\x59\\n'")
        self.assertIn("TTY\r\n", output)
        output = session.command("false")
        self.assertIn("!1", output)
        output = session.command("printf '\\x53\\x54\\x41\\x54\\x55\\x53=%s\\n' \"$?\"")
        self.assertIn("STATUS=1\r\n", output)
        self.assertIn("!127 command not found", session.command("bacumi_nonexistent_command_fixture"))
        self.assertIn("STATUS=127\r\n", session.command("printf '\\x53\\x54\\x41\\x54\\x55\\x53=%s\\n' \"$?\""))
        project = self.cwd / "spațiu 日本語 with spaces"
        project.mkdir()
        session.command("cd -- " + shlex.quote(str(project)))
        self.assert_pwd(session, project)
        for columns in (40, 80, 120):
            session.resize(columns)
            self.assert_pwd(session, project)
            output = session.command("printf '\\x43\\x4f\\x4c\\x53=%s\\n' \"$COLUMNS\"")
            self.assertIn(f"COLS={columns}\r\n", output)
        session.send("print -r -- 'multiline\n")
        session.send("日本語'\n")
        session.read_until(EXECUTING)
        output = session.read_until()
        self.assertIn("multiline\r\n日本語\r\n", output)
        session.send("unexecuted partial command")
        # PROMPT is printed before ZLE enables input. Wait for the editor to
        # echo this buffer before Ctrl-C; otherwise the terminal driver can
        # flush both writes before ZLE sees either, especially on Linux.
        session.read_until(b"partial command")
        session.send(b"\x03")
        session.read_until()
        self.assert_pwd(session, project)
        session.send("/bin/sh -c 'printf \"\\033]777;bacumi-test-sleep\\007\"; exec /bin/sleep 10'\n")
        # The foreground child writes this only after Zsh starts the job.
        session.read_until(b"\x1b]777;bacumi-test-sleep\x07")
        session.send(b"\x03")
        output = session.read_until()
        self.assertIn("!130 interrupted", output)
        self.assert_pwd(session, project)

    def test_runtime_stdin_is_closed_and_hanging_probes_are_bounded(self):
        project = self.cwd / "all-runtimes"
        project.mkdir()
        for filename in ("package.json", "pyproject.toml", "go.mod", "Cargo.toml", "global.json"):
            (project / filename).write_text("{}\n")
        for action in ("read", "hang"):
            with self.subTest(action=action):
                session = self.start(extra_env={"PROBE_ACTION_" + tool: action
                                                for tool in ("node", "python3", "go", "rustc", "dotnet")})
                session.command("cd -- " + shlex.quote(str(project)))
                self.assert_pwd(session, project)
                session.command("cd -- " + shlex.quote(str(self.cwd)))
                self.assert_pwd(session, self.cwd)

    def test_each_runtime_handles_stdin_reader_and_hanging_executable(self):
        manifests = {"node": "package.json", "python3": "pyproject.toml",
                     "go": "go.mod", "rustc": "Cargo.toml", "dotnet": "global.json"}
        for action in ("read", "hang"):
            session = self.start(extra_env={"PROBE_ACTION_" + tool: action for tool in manifests})
            for tool, filename in manifests.items():
                with self.subTest(action=action, tool=tool):
                    project = self.cwd / f"{action}-{tool}"
                    project.mkdir()
                    (project / filename).write_text("{}\n")
                    session.command("cd -- " + shlex.quote(str(project)))
                    self.assert_pwd(session, project)
                    probes = self.probe_log.read_text().splitlines()
                    self.assertTrue(any(line.startswith(tool + " ") for line in probes), tool)
                    if action == "read":
                        self.assertTrue(any(line.startswith(tool + " ") and line.endswith(" eof")
                                            for line in probes), f"{tool} did not receive EOF on stdin")
                    session.command("cd -- " + shlex.quote(str(self.cwd)))
                    self.assert_pwd(session, self.cwd)
            session.close()

    def test_slow_git_probe_does_not_freeze_prompt_or_steal_commands(self):
        session = self.start(extra_env={"PROBE_ACTION_git": "hang"})
        self.assert_pwd(session, self.cwd)
        session.command("false")
        self.assertIn("STATUS=1\r\n", session.command("printf '\\x53\\x54\\x41\\x54\\x55\\x53=%s\\n' \"$?\""))
        self.assertIn("JOBS=0\r\n", session.command("printf '\\x4a\\x4f\\x42\\x53=%s\\n' \"${#jobstates}\""))

    def test_real_git_status_with_terminal_session_exit_hooks(self):
        real_git = shutil.which("git")
        wrapper = self.tools / "git"
        wrapper.write_text("#!/bin/sh\nexec " + shlex.quote(real_git) + ' "$@"\n')
        project = self.cwd / "real git project"
        project.mkdir()
        def git(*args):
            subprocess.run([real_git, "-c", "core.hooksPath=/dev/null", "-c", "commit.gpgsign=false", *args],
                           cwd=project, check=True, capture_output=True, timeout=5)
        git("init", "--initial-branch=fixture-main")
        (project / "tracked").write_text("original\n")
        git("add", "tracked")
        git("-c", "user.name=Bacumi", "-c", "user.email=tests@example.invalid", "commit", "-m", "fixture")
        (project / "tracked").write_text("changed\n")
        (project / "staged").write_text("staged\n")
        git("add", "staged")
        (project / "untracked").write_text("untracked\n")
        for mode in ("dark", "light"):
            with self.subTest(mode=mode):
                session = self.start(mode)
                # The macOS temporary path is long; leave room for all counts.
                session.resize(240)
                session.command("bacumi_session_exit() { print -r -- 'Saving session...'; }; add-zsh-hook zshexit bacumi_session_exit")
                output = session.command("cd -- " + shlex.quote(str(project)))
                self.assertIn("git:fixture-main +1 ~1 ?1", output)
                self.assertNotIn("status:?", output)
                self.assertNotIn("Saving session...", output)
                self.assert_pwd(session, project)
                session.close()

    def test_timed_out_probe_kills_children_without_polluting_jobs(self):
        project = self.cwd / "process-tree"
        project.mkdir()
        (project / "package.json").write_text("{}\n")
        session = self.start(extra_env={"PROBE_ACTION_node": "tree"})
        session.command("cd -- " + shlex.quote(str(project)))
        self.assert_pwd(session, project)
        records = [line.split() for line in self.probe_log.read_text().splitlines()]
        self.assertTrue(any(record[0] == "node-child" for record in records),
                        "The fixture must spawn its child before the timeout")
        pids = {int(record[1]) for record in records if record[0].startswith("node")}
        deadline = time.monotonic() + 1.0
        while pids and time.monotonic() < deadline:
            for pid in tuple(pids):
                try:
                    os.kill(pid, 0)
                except ProcessLookupError:
                    pids.remove(pid)
            if pids:
                time.sleep(.01)
        self.assertFalse(pids, f"Timed-out runtime probe left fixture processes alive: {pids}")
        output = session.command("printf '\\x4a\\x4f\\x42\\x53=%s\\n' \"${#jobstates}\"")
        self.assertIn("JOBS=0\r\n", output)


if __name__ == "__main__":
    unittest.main()
