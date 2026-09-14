#!/usr/bin/python3
"""Set automatic Live startup before live-build computes image checksums."""
import argparse,re
from pathlib import Path

def configure(root):
    entries=[]
    for path in sorted(root.rglob('*.cfg')):
        blocks=re.split(r'(?im)^label\s+',path.read_text(errors='replace'))[1:]
        for block in blocks:
            label=block.splitlines()[0].strip()
            if 'boot=live' in block and 'failsafe' not in label.lower() and 'fail-safe' not in block.lower():entries.append(label)
    if not entries:raise ValueError('Live boot label not found')
    configs=list(root.rglob('isolinux.cfg'))+list(root.rglob('syslinux.cfg'))
    if not configs:raise ValueError('Syslinux configuration not found')
    for path in configs:
        with path.open('a') as out:out.write(f'\n# ReaperGrasp unattended startup\ndefault {entries[0]}\nontimeout {entries[0]}\nprompt 0\ntimeout 30\n')
    for path in root.rglob('grub.cfg'):
        with path.open('a') as out:out.write('\nset default=0\nset timeout=3\n')
    print('Automatic live boot:',entries[0])
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',nargs='?',type=Path,default=Path('binary'));configure(p.parse_args().root)
