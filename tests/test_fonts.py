"""Isolated optional font installation; never touches the user's font directory."""
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
NAMES = [f'MesloLGS NF {style}.ttf' for style in ('Regular', 'Bold', 'Italic', 'Bold Italic')]

class FontInstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'source'; self.source.mkdir()
        self.target = self.root / 'fonts'
        self.manifest = self.root / 'manifest.tsv'
        lines = []
        for name in NAMES:
            data = ('fixture ' + name).encode()
            (self.source / name).write_bytes(data)
            lines.append(f'{hashlib.sha256(data).hexdigest()}\t{name}\thttps://example.invalid/{name.replace(" ", "%20")}\n')
        self.manifest.write_text(''.join(lines))

    def run_install(self, *extra, ok=True, env=None):
        result = subprocess.run(['sh', str(ROOT / 'install-font.sh'), '--font-dir', str(self.target), '--source-dir', str(self.source), '--manifest', str(self.manifest), *extra], text=True, capture_output=True, env=env)
        self.assertEqual(result.returncode == 0, ok, result.stdout + result.stderr)
        return result

    def test_repeat_uninstall_and_notices(self):
        self.run_install(); self.run_install()
        for name in NAMES: self.assertEqual((self.target/name).read_bytes(), (self.source/name).read_bytes())
        self.assertTrue((self.target/'Bacumi-MesloLGS-NF/Apache-2.0.txt').is_file())
        (self.target/'other.ttf').write_text('third party')
        self.run_install('--uninstall')
        self.assertEqual(sorted(p.name for p in self.target.iterdir()), ['other.ttf'])

    def test_preserves_existing_matching_font(self):
        self.target.mkdir(); name = NAMES[0]
        (self.target/name).write_bytes((self.source/name).read_bytes())
        self.run_install(); self.run_install('--uninstall')
        self.assertTrue((self.target/name).is_file())

    def test_failure_before_destination_mutation(self):
        (self.source/NAMES[-1]).write_text('corrupted')
        self.run_install(ok=False)
        self.assertFalse(self.target.exists())

    def test_partial_download_and_conflicting_font(self):
        (self.source/NAMES[-1]).unlink()
        self.run_install(ok=False); self.assertFalse(self.target.exists())
        (self.source/NAMES[-1]).write_bytes(('fixture '+NAMES[-1]).encode())
        self.target.mkdir(); (self.target/NAMES[0]).write_text('someone else')
        self.run_install(ok=False)
        self.assertEqual(len(list(self.target.iterdir())), 1)

    def test_local_edits_and_symlinks_are_protected(self):
        self.run_install(); (self.target/NAMES[0]).write_text('edited')
        self.run_install(ok=False); self.run_install('--uninstall',ok=False)
        self.assertTrue((self.target/NAMES[-1]).exists())

    def test_rejects_unsafe_manifest(self):
        self.manifest.write_text(self.manifest.read_text().replace(NAMES[0], '../escape.ttf'))
        self.run_install(ok=False); self.assertFalse(self.target.exists())

    def test_symlink_target_and_notice_directory(self):
        other = self.root/'other'; other.mkdir()
        self.target.symlink_to(other, target_is_directory=True)
        self.run_install(ok=False)
        self.assertFalse(list(other.iterdir()))
        self.target.unlink(); self.target.mkdir()
        (self.target/'Bacumi-MesloLGS-NF').symlink_to(other, target_is_directory=True)
        self.run_install(ok=False)
        self.assertFalse(list(other.iterdir()))

    def test_owned_upgrade_and_preexisting_font(self):
        self.target.mkdir()
        (self.target/NAMES[0]).write_bytes((self.source/NAMES[0]).read_bytes())
        self.run_install()
        old = self.manifest.read_text()
        data = b'upgraded owned font'
        (self.source/NAMES[1]).write_bytes(data)
        self.manifest.write_text(old.replace(hashlib.sha256(('fixture '+NAMES[1]).encode()).hexdigest(), hashlib.sha256(data).hexdigest()))
        self.run_install()
        self.assertEqual((self.target/NAMES[1]).read_bytes(), data)
        self.run_install('--uninstall')
        self.assertTrue((self.target/NAMES[0]).exists())

    def failing_operation_environment(self, operation, name):
        tools = self.root/'tools'; tools.mkdir()
        wrapper = tools/operation
        wrapper.write_text('#!/bin/sh\nfor last do :; done\n'
                           'if [ "$last" = "$FONT_FAIL_TARGET" ] && [ ! -e "$FONT_FAIL_ONCE" ]; then\n'
                           ' touch "$FONT_FAIL_ONCE"; exit 1\nfi\n'
                           f'exec /bin/{operation} "$@"\n')
        wrapper.chmod(0o755)
        return {**os.environ, 'PATH': str(tools)+os.pathsep+os.environ['PATH'],
                'FONT_FAIL_TARGET': str(self.target/name), 'FONT_FAIL_ONCE': str(self.root/'failed')}

    def test_failed_copy_rolls_back_installed_changes(self):
        env = self.failing_operation_environment('cp', NAMES[2])
        self.run_install(ok=False, env=env)
        self.assertFalse(self.target.exists(), 'Failed install left partial font files')

    def test_failed_update_restores_owned_version(self):
        self.run_install()
        before = {str(p.relative_to(self.target)): p.read_bytes() for p in self.target.rglob('*') if p.is_file()}
        data = b'updated font version'
        previous_digest = hashlib.sha256((self.source/NAMES[0]).read_bytes()).hexdigest()
        (self.source/NAMES[0]).write_bytes(data)
        self.manifest.write_text(self.manifest.read_text().replace(previous_digest, hashlib.sha256(data).hexdigest()))
        env = self.failing_operation_environment('cp', NAMES[1])
        self.run_install(ok=False, env=env)
        after = {str(p.relative_to(self.target)): p.read_bytes() for p in self.target.rglob('*') if p.is_file()}
        self.assertEqual(after, before, 'Failed update did not restore the installed font version')

    def test_failed_unlink_rolls_back_installed_changes(self):
        self.run_install()
        before = {str(p.relative_to(self.target)): p.read_bytes() for p in self.target.rglob('*') if p.is_file()}
        env = self.failing_operation_environment('rm', NAMES[1])
        self.run_install('--uninstall', ok=False, env=env)
        after = {str(p.relative_to(self.target)): p.read_bytes() for p in self.target.rglob('*') if p.is_file()}
        self.assertEqual(after, before, 'Failed uninstall left missing fonts or ownership')

    def test_offline_uninstall(self):
        self.run_install()
        for path in self.source.iterdir(): path.unlink()
        self.run_install('--uninstall')

if __name__ == '__main__': unittest.main()
