"""Adversarial local process fixtures for bounded native prompt probes."""
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile
import time
import unittest

ROOT=Path(__file__).resolve().parents[1]
ZSH=shutil.which('zsh')

class ProbeSafety(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='bacumi safety ');self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)

    def run_zsh(self,script,extra=None):
        env={**os.environ,'THEME_FILE':str(ROOT/'bacumi-developer-dark.zsh-theme'),'TERM':'dumb','NO_COLOR':'1','BACUMI_SHOW_RUNTIMES':'0',**(extra or {})}
        return subprocess.run([ZSH,'-dfc','source "$THEME_FILE"; '+script],env=env,cwd=self.root,capture_output=True,timeout=3)

    def test_input_failure_output_bounds_and_manager_settings(self):
        cases=[("if read value; then exit 12; fi; printf v22.4.0",0,b'v22.4.0'),
               ('printf v22.4.0; exit 17',17,b''),
               ('while :; do printf 012345678901234567890123456789; done',124,b''),
               ('exec /bin/sleep 2',124,b''),
               ('printf "v22.4.0\\n\\0BACUMI_EXIT=0\\0"; /bin/sleep 1; exit 9',124,b'')]
        for command,code,expected in cases:
            with self.subTest(command=command):
                result=self.run_zsh('_bacumi_developer_probe 4096 /bin/sh -c "$PROBE_COMMAND"; saved=$?; print -r -- "code=$saved"; print -rn -- "$_bacumi_developer_probe_output"',{'PROBE_COMMAND':command})
                self.assertEqual(result.returncode,0,result.stderr)
                self.assertEqual(result.stdout,b'code='+str(code).encode()+b'\n'+expected)
        result=self.run_zsh('_bacumi_developer_probe 4096 /bin/sh -c \'printf "%s|%s|%s|%s" "$GOTOOLCHAIN" "$RUSTUP_AUTO_INSTALL" "$DOTNET_CLI_TELEMETRY_OPTOUT" "$GIT_TERMINAL_PROMPT"\'; print -rn -- "$_bacumi_developer_probe_output"')
        self.assertEqual(result.stdout,b'local|0|1|0')

    def test_successful_probe_cleans_child_and_cleanup_uses_builtins(self):
        pid_file=self.root/'child pid'
        script='''kill() { /bin/sleep 2; return 1; }
_bacumi_developer_probe 4096 /bin/sh -c '/bin/sleep 5 >/dev/null 2>&1 & printf "%s" "$!" > "$PROBE_PID_FILE"; printf v22.4.0'
print -r -- "code=$?"
print -r -- "$_bacumi_developer_probe_output"
_bacumi_developer_probe 4096 /bin/sh -c 'exec /bin/sleep 2'
print -r -- "timeout=$?"
'''
        start=time.monotonic();result=self.run_zsh(script,{'PROBE_PID_FILE':str(pid_file)})
        self.assertLess(time.monotonic()-start,1.2)
        self.assertEqual(result.stdout,b'code=0\nv22.4.0\ntimeout=124\n',result.stderr)
        pid=int(pid_file.read_text())
        deadline=time.monotonic()+.6
        alive=True
        while time.monotonic()<deadline:
            try:os.kill(pid,0)
            except ProcessLookupError:alive=False;break
            time.sleep(.02)
        if alive:
            try:os.kill(pid,signal.SIGKILL)
            except ProcessLookupError:pass
        self.assertFalse(alive,'Probe left a background child after successful version output')

    def test_probe_does_not_run_parent_shell_exit_hooks(self):
        # Native terminal session saving and custom hooks can write after the
        # worker's NUL-framed exit status, making a successful probe look timed out.
        for setup in (
            'zshexit() { bacumi_fixture_exit; }',
            'add-zsh-hook zshexit bacumi_fixture_exit',
            "trap 'bacumi_fixture_exit' EXIT",
        ):
            with self.subTest(setup=setup):
                log=self.root/'exit hooks'
                if log.exists():log.unlink()
                script='''bacumi_fixture_exit() {
  builtin print -r -- called >> "$EXIT_LOG"
  builtin print -r -- 'Saving session...'
  builtin print -r -- 'Saving history...' >&2
}
'''+setup+'''
_bacumi_developer_probe 4096 /bin/sh -c 'printf "record\\000final\\000"'
builtin print -r -- "code=$?"
[[ $_bacumi_developer_probe_output == $'record\\0final\\0' ]] && builtin print -r -- exact
'''
                result=self.run_zsh(script,{'EXIT_LOG':str(log)})
                self.assertEqual(result.stdout,b'code=0\nexact\nSaving session...\n',result.stderr)
                self.assertEqual(log.read_text().splitlines(),['called'],
                                 'Only the parent shell should run its exit hook')

    def test_head_fallback_without_git_and_rejection_of_malformed_records(self):
        git=self.root/'.git';git.mkdir()
        for text,expected in [('ref: refs/heads/main\n','git:main status:?'),('a'*40+'\n','git:@aaaaaaa status:?'),('b'*64+'\n','git:@bbbbbbb status:?'),('abc\n',None),('ref: refs/heads/'+'a'*600+'\n',None)]:
            with self.subTest(head=text[:30]):
                (git/'HEAD').write_text(text)
                result=self.run_zsh('PATH=/nonexistent; true; _bacumi_developer_precmd; print -rP -- "$PROMPT"')
                self.assertEqual(result.returncode,0,result.stderr)
                if expected:self.assertIn(expected.encode(),result.stdout)
                else:self.assertNotIn(b'git:',result.stdout)

    def test_raw_c1_bytes_are_removed_without_damaging_unicode(self):
        env={os.fsencode(k):os.fsencode(v) for k,v in os.environ.items()}
        env.update({b'LC_ALL':b'en_US.UTF-8',b'THEME_FILE':os.fsencode(ROOT/'bacumi-developer-dark.zsh-theme'),b'RAW':b'a\x9b31m '+ '☕ 漢字 café'.encode()})
        result=subprocess.run([ZSH,'-dfc','source "$THEME_FILE"; _bacumi_developer_bang=off; _bacumi_developer_escape "$RAW"; print -rn -- "$REPLY"'],env=env,capture_output=True,timeout=3)
        self.assertEqual(result.stdout,b'a?31m '+ '☕ 漢字 café'.encode(),result.stderr)

if __name__=='__main__':unittest.main()
