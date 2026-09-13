"""Recording-level split, chronological windows, no shared frames across splits."""
import hashlib
import json
import random
from pathlib import Path
import cv2
import numpy as np
import torch
from torch.utils.data import Dataset,DataLoader
from config import Config

def index_manifest(path,seq_length=16):
    path=Path(path);records=json.loads(path.read_text());groups={};hashes={};windows={'train':[],'val':[]}
    for record in records:
        split=record['split'];group=record['group'];label=record['label']
        if split not in windows or not isinstance(label,int) or not 0<=label<5:raise ValueError('Invalid split or label')
        if group in groups and groups[group]!=split:raise ValueError('Recording group leaks across splits')
        groups[group]=split
        frames=record['frames'];numbers=[f['index'] for f in frames]
        if numbers!=sorted(set(numbers)):raise ValueError('Frame indices must be unique and chronological')
        paths=[]
        for frame in frames:
            image=(path.parent/frame['path']).resolve();digest=hashlib.sha256(image.read_bytes()).hexdigest()
            if digest in hashes and hashes[digest]!=split:raise ValueError('Duplicate frame leaks across splits')
            hashes[digest]=split;paths.append(image)
        for start in range(0,len(paths)-seq_length+1):
            indices=numbers[start:start+seq_length]
            if any(b!=a+1 for a,b in zip(indices,indices[1:])):continue
            windows[split].append((paths[start:start+seq_length],label))
    if not all(windows.values()):raise ValueError('Both train and validation need complete windows')
    return windows

class VideoSequenceDataset(Dataset):
    def __init__(self,samples,augment=False):self.samples=samples;self.augment=augment
    def __len__(self):return len(self.samples)
    def __getitem__(self,index):
        paths,label=self.samples[index];frames=[]
        # One transform for the entire temporal window.
        flip=self.augment and random.random()<.5
        gain=random.uniform(.9,1.1) if self.augment else 1
        for path in paths:
            frame=cv2.imread(str(path))
            if frame is None:raise ValueError(f'Unreadable image: {path}')
            frame=cv2.cvtColor(cv2.resize(frame,(640,640)),cv2.COLOR_BGR2RGB)
            if flip:frame=cv2.flip(frame,1)
            frame=np.clip(frame.astype(np.float32)*gain/255,0,1)
            frames.append(torch.from_numpy(frame).permute(2,0,1))
        return torch.stack(frames),torch.tensor(label,dtype=torch.long)

def create_dataloaders(manifest=None):
    manifest=Path(manifest or Config.DATA_ROOT/'recordings.json')
    if not manifest.exists():raise FileNotFoundError('Provide recordings.json with group/split/label/chronological frames; automatic random window splitting is disabled')
    windows=index_manifest(manifest,Config.SEQ_LENGTH)
    return tuple(DataLoader(VideoSequenceDataset(windows[s],s=='train'),batch_size=Config.BATCH_SIZE,shuffle=s=='train',num_workers=0) for s in ('train','val'))
