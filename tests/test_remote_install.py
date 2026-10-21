"""Exercise remote install/update with local ZIPs; no network or user files."""
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
FILES = ['install.sh', 'bacumi-dark.zsh-theme', 'bacumi-light.zsh-theme',
         'bacumi-developer-dark.zsh-theme', 'bacumi-developer-light.zsh-theme',
         'lib/prompt.zsh', 'lib/developer-prompt.zsh', 'lib/probe.zsh']


class RemoteInstall(unittest.TestCase):
    def test_verified_install_update_corruption_and_download_failure(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            version = (ROOT / 'VERSION').read_text().strip()
            self.assertIn('version=' + version, (ROOT / 'install-remote.sh').read_text())
            name = 'bacumi-oh-my-zsh-theme-' + version
            archive = folder / (name + '.zip')
            with zipfile.ZipFile(archive, 'w') as package:
                for relative in FILES:
                    package.write(ROOT / relative, name + '/' + relative)
            (folder / 'SHA256SUMS').write_text(hashlib.sha256(archive.read_bytes()).hexdigest() + '  ' + name + '.zip\n')
            tools = folder / 'bin'
            tools.mkdir()
            curl = tools / 'curl'
            curl.write_text('''#!/bin/sh
[ "${DOWNLOAD_FAIL:-0}" = 0 ] || exit 22
for arg do
 case "$arg" in https://*) file=${arg##*/};; esac
 done
while [ "$1" != -o ]; do shift; done
cp "$FIXTURE/$file" "$2"
''')
            curl.chmod(0o755)
            env = {**os.environ, 'PATH': str(tools) + os.pathsep + os.defpath, 'FIXTURE': str(folder), 'HOME': str(folder)}
            custom = folder / 'custom space'
            command = ['sh', str(ROOT / 'install-remote.sh'), '--custom-dir', str(custom)]
            for _ in range(2):
                subprocess.run(command, env=env, capture_output=True, check=True, timeout=10)
            installed = custom / 'themes/bacumi'
            before = {p.relative_to(installed): p.read_bytes() for p in installed.rglob('*') if p.is_file()}
            archive.write_bytes(b'corrupt download')
            for extra in ({}, {'DOWNLOAD_FAIL': '1'}):
                result = subprocess.run(command, env={**env, **extra}, capture_output=True, timeout=10)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(before, {p.relative_to(installed): p.read_bytes() for p in installed.rglob('*') if p.is_file()})

    def test_upgrade_six_file_receipt(self):
        with tempfile.TemporaryDirectory() as temporary:
            custom = Path(temporary)
            command = ['sh', str(ROOT / 'install.sh'), '--custom-dir', str(custom)]
            subprocess.run(command, check=True, capture_output=True)
            target = custom / 'themes/bacumi'
            marker = target / '.bacumi-installed'
            marker.write_text(''.join(line for line in marker.read_text().splitlines(keepends=True) if not line.startswith('lib/probe.zsh ')))
            (target / 'lib/probe.zsh').unlink()
            subprocess.run(command, check=True, capture_output=True)
            self.assertTrue((target / 'lib/probe.zsh').is_file())

    def test_failed_update_restores_owned_files_and_receipt(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            source = folder / 'source'
            for relative in FILES:
                target = source / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / relative, target)
            custom = folder / 'custom'
            command = ['sh', str(source / 'install.sh'), '--custom-dir', str(custom)]
            subprocess.run(command, check=True, capture_output=True)
            installed = custom / 'themes/bacumi'
            before = {p.relative_to(installed): p.read_bytes() for p in installed.rglob('*') if p.is_file()}
            (source / 'bacumi-dark.zsh-theme').write_text('# new version\n')
            tools = folder / 'bin'
            tools.mkdir()
            cp = tools / 'cp'
            cp.write_text('''#!/bin/sh
for arg do last=$arg; done
case "$last" in
 */themes/bacumi/lib/prompt.zsh)
  if [ ! -e "$FAIL_ONCE" ]; then touch "$FAIL_ONCE"; exit 1; fi;;
esac
exec /bin/cp "$@"
''')
            cp.chmod(0o755)
            env = {**os.environ, 'PATH': str(tools) + os.pathsep + os.defpath, 'FAIL_ONCE': str(folder / 'failed')}
            result = subprocess.run(command, env=env, capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(before, {p.relative_to(installed): p.read_bytes() for p in installed.rglob('*') if p.is_file()})
            subprocess.run(command, check=True, capture_output=True)
