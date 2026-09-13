"""Offline folder replay through the same validated runtime as the GUI."""
import argparse
import json
import re
import time
from pathlib import Path
import cv2
from reapergrasp.cameras import natural
from reapergrasp.model import ModelEngine
from reapergrasp.settings import Settings

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--device',choices=['auto','cpu','cuda'],default='auto')
    args=parser.parse_args();engine=ModelEngine(Settings(device=args.device));args.output.mkdir(parents=True,exist_ok=True)
    paths=sorted([p for p in args.input.iterdir() if p.suffix.lower() in {'.jpg','.jpeg','.png'}],key=natural)
    if not paths:raise ValueError('No input images')
    report=[];previous=None
    for n,path in enumerate(paths):
        numbers=re.findall(r'\d+',path.stem)
        if not numbers:raise ValueError('Filenames must end with chronological frame numbers')
        index=int(numbers[-1])
        if previous is not None and index!=previous+1:engine.reset('folder')
        previous=index;frame=cv2.imread(str(path))
        if frame is None:raise ValueError(f'Unreadable frame: {path}')
        start=time.perf_counter();result=engine.infer('folder',frame,n*.5+1)
        result.update(file=path.name,seconds=time.perf_counter()-start);report.append(result)
    (args.output/'frames.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print(f'{len(report)} frames processed; results: {args.output / "frames.json"}')
if __name__=='__main__':main()
