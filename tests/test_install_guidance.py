"""Check migration guidance without ever sourcing or changing user configuration."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]

class ConfigGuidance(unittest.TestCase):
    def test_powerlevel10k_instant_prompt_detection_is_read_only(self):
        with tempfile.TemporaryDirectory() as temporary:
            home=Path(temporary)
            config=home/'.zshrc'
            text='''if [[ -r "$HOME/.cache/p10k-instant-prompt-user.zsh" ]]; then
  source "$HOME/.cache/p10k-instant-prompt-user.zsh"
fi
ZSH_THEME="bacumi/bacumi-developer-dark"
plugins=(git extract)
'''
            config.write_text(text)
            env={**os.environ,'HOME':str(home),'ZDOTDIR':str(home)}
            result=subprocess.run(['sh',str(ROOT/'install.sh'),'--check-config'],env=env,text=True,capture_output=True,timeout=3)
            self.assertEqual(result.returncode,1,result.stdout+result.stderr)
            self.assertIn('Powerlevel10k',result.stdout+result.stderr)
            self.assertIn('instant',result.stdout+result.stderr)
            self.assertEqual(config.read_text(),text)
            self.assertFalse((home/'.oh-my-zsh').exists())
            config.write_text('# source "$HOME/.cache/p10k-instant-prompt-user.zsh"\n# source ~/.p10k.zsh\nZSH_THEME="bacumi/bacumi-developer-dark"\nplugins=(git extract)\n')
            result=subprocess.run(['sh',str(ROOT/'install.sh'),'--check-config'],env=env,text=True,capture_output=True,timeout=3)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertIn('No active Powerlevel10k',result.stdout)

if __name__=='__main__':unittest.main()
