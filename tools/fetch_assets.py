"""Verified build-time downloads; no runtime network dependency."""
import hashlib,json,os,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BASE='https://raw.githubusercontent.com/SymplysoF/HarvesterVisualizer/70410a054a6e6bc96e8c2b3c4c9935f9ade4c1a6/'
def main():
    for asset in json.loads((ROOT/'docs/upstream-assets.json').read_text()):
        relative=asset['path'];target=ROOT/relative.replace('workspace/demo/','examples/replay/')
        if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest()==asset['sha256']:continue
        target.parent.mkdir(parents=True,exist_ok=True);temp=target.with_suffix(target.suffix+'.part')
        try:
            with urllib.request.urlopen(BASE+relative,timeout=120) as response,temp.open('wb') as output:
                while chunk:=response.read(1024*1024):output.write(chunk)
            if hashlib.sha256(temp.read_bytes()).hexdigest()!=asset['sha256']:raise ValueError(f'Checksum mismatch: {relative}')
            os.replace(temp,target)
        finally:temp.unlink(missing_ok=True)
if __name__=='__main__':main()
