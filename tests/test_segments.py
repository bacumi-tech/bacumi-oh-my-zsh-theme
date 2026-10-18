"""Exercise actual Zsh badge rendering with shared, controlled semantic fixtures."""
import json
import os
from pathlib import Path
import re
import subprocess
import unicodedata
import unittest

ROOT = Path(__file__).resolve().parents[1]
ANSI = re.compile(r'\x1b\[[0-9;]*m')
CASES = json.loads((ROOT/'tests/fixtures/prompt-segments.json').read_text())


def width(text):
    return sum(0 if unicodedata.combining(c) else 2 if unicodedata.east_asian_width(c) in 'WF' else 1 for c in text)


def render(case, columns=120, appearance='dark', layout='developer', mode='truecolor', icons=False, extra=None):
    records = f'# branch.oid abcdef1234567890\0# branch.head {case["branch"]}\0# branch.ab +1 -2\0'
    if not case.get('unavailable'):
        records += '1 M. N... 100644 100644 100644 a b staged\0'*2
        records += '1 .M N... 100644 100644 100644 a b unstaged\0'
        records += '? new\0'*3
    records += 'u UU N... conflict\0'*case['conflicts']
    # Environment strings cannot contain NUL; the parser also accepts lines.
    records = records.replace('\0','\n')
    env = {**os.environ, 'TERM':'xterm-256color', 'COLORTERM':'truecolor','NO_COLOR':'',
           'THEME_FILE':str(ROOT/f'bacumi-developer-{appearance}.zsh-theme'),
           'FIXTURE_GIT':records, 'FIXTURE_DIR':case['directory'],
           'FIXTURE_OPERATION':case['operation'], 'FIXTURE_CONTEXT':'  '.join(case['context']),
           'FIXTURE_EXIT':str(case['exit']), 'FIXTURE_UNAVAILABLE':str(int(case.get('unavailable',False))),
           'FIXTURE_DURATION':str(case['duration']), 'FIXTURE_WIDTH':str(columns),
           'BACUMI_PROMPT_LAYOUT':layout, 'BACUMI_COLOR_MODE':mode,
           'BACUMI_PROMPT_ICONS':str(int(icons)), **(extra or {})}
    script = '''source "$THEME_FILE"
commands[git]=/bin/true
_bacumi_developer_probe() { _bacumi_developer_probe_output=$FIXTURE_GIT; return 0; }
functions[_bacumi_fixture_parse]=$functions[_bacumi_developer_parse_git]
_bacumi_developer_parse_git() { _bacumi_fixture_parse "$1"; _bacumi_developer_git[unavailable]=$FIXTURE_UNAVAILABLE; }
_bacumi_developer_operation() { REPLY=$FIXTURE_OPERATION; }
_bacumi_developer_runtimes() { REPLY=$FIXTURE_CONTEXT; }
PWD=$FIXTURE_DIR
COLUMNS=$FIXTURE_WIDTH
_bacumi_developer_started=$((EPOCHREALTIME-FIXTURE_DURATION))
(exit $FIXTURE_EXIT)
_bacumi_developer_precmd
print -rnP -- "$PROMPT"
'''
    result = subprocess.run(['zsh','-dfc',script],env=env,text=True,capture_output=True,timeout=3)
    if result.returncode: raise AssertionError(result.stderr)
    return result.stdout


class Segments(unittest.TestCase):
    def test_shared_matrix(self):
        for appearance in ('dark','light'):
            for layout in ('developer','compact'):
                for mode in ('truecolor','ansi','none'):
                    for icons in (False,True):
                        for case in CASES:
                            for columns in (40,80,120):
                                with self.subTest(appearance=appearance,layout=layout,mode=mode,icons=icons,case=case['name'],columns=columns):
                                    raw=render(case,columns,appearance,layout,mode,icons)
                                    plain=ANSI.sub('',raw)
                                    self.assertIn('git:',plain)
                                    self.assertTrue(all(width(line)<=columns for line in plain.splitlines()),repr(plain))
                                    if case['conflicts']:self.assertIn('conflict:1',plain)
                                    if case.get('unavailable'):
                                        self.assertIn('status:?',plain)
                                        for token in ('+2','~1','?3','ahead:','behind:'):self.assertNotIn(token,plain)
                                    if not case['success']:self.assertIn('!'+str(case['exit']),plain)
                                    self.assertTrue(plain.endswith(('❯' if icons else '>')+' '),repr(plain))
                                    if mode=='none':self.assertNotIn('\x1b',raw)
                                    elif mode=='truecolor':self.assertIn('48;2;',raw)
                                    else:self.assertIn('\x1b[7m',raw)
                                    if case['name']=='developer-clean' and columns==120:
                                        for token in ('+2','~1','?3','ahead:1','behind:2','node:22.4.0','3.2s'):self.assertIn(token,plain)
                                    if case['name']=='developer-clean' and columns==80:self.assertIn('node:22.4.0',plain)

    def test_exact_colors_controls_and_plain_fallbacks(self):
        for appearance in ('dark','light'):
            palette=json.loads((ROOT/'palette.json').read_text())['variants'][appearance]
            raw=render(CASES[0],appearance=appearance)
            for role in ('accent','git','selection'):
                value=palette[role].lstrip('#');rgb=';'.join(str(int(value[i:i+2],16)) for i in (0,2,4))
                self.assertIn('48;2;'+rgb+'m',raw)
            for settings in ({'TERM':'dumb'},{'NO_COLOR':'1'}):self.assertNotIn('\x1b',render(CASES[0],appearance=appearance,extra=settings))
        raw=render(CASES[2],mode='none')
        self.assertIn('$(unsafe)%',raw)
        self.assertNotIn('\x1b',raw)

if __name__=='__main__':unittest.main()
