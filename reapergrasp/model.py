"""One inference owner; no downloads or changes to global Config at startup."""
import os
import hashlib
import json
import logging
from pathlib import Path
from .decision import decide

log=logging.getLogger(__name__)


def verify_bundle(path):
    path=Path(path); manifest=json.loads((path/'manifest.json').read_text())
    if manifest.get('seq_length')!=16 or manifest.get('classes')!=['connection','foreign','garbage','point','normal']:
        raise ValueError('Unsupported model contract')
    for name in ['yolo.pt','autoencoder_model.pth','best_complete_model_fixed.pth']:
        h=hashlib.sha256()
        with (path/name).open('rb') as f:
            for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
        if h.hexdigest()!=manifest['sha256'][name]:raise ValueError(f'Model checksum mismatch: {name}')
    return manifest


def choose_device(torch, requested='auto'):
    if requested=='cpu':return 'cpu',None
    try:
        if not torch.cuda.is_available():return 'cpu','CUDA unavailable'
        # is_available alone does not prove usable kernels/driver/architecture.
        a=torch.ones((32,32),device='cuda'); _=a@a;torch.cuda.synchronize()
        return 'cuda',None
    except Exception as exc:
        return 'cpu',f'CUDA probe failed: {exc}'


class ModelEngine:
    def __init__(self, settings):
        os.environ['YOLO_OFFLINE']='true'
        import torch
        self.torch=torch;torch.set_num_threads(settings.threads)
        self.settings=settings
        self.manifest=verify_bundle(settings.model_dir)
        self.device,self.fallback_reason=choose_device(torch,settings.device)
        self.histories={};self.timestamps={}
        try:self._load()
        except Exception as exc:
            if self.device!='cuda':raise
            self.device='cpu';self.fallback_reason=f'GPU model initialization failed: {exc}'
            self._load()

    def _load(self):
        from ultralytics import YOLO
        from complete_model import CompleteDefectDetector
        path=Path(self.settings.model_dir)
        self.yolo=YOLO(str(path/'yolo.pt'))
        self.complete=CompleteDefectDetector(yolo_path=path/'yolo.pt',ae_path=path/'autoencoder_model.pth',device=self.device)
        checkpoint=self.torch.load(path/'best_complete_model_fixed.pth',map_location='cpu',weights_only=True)
        self.complete.load_state_dict(checkpoint['model_state_dict'],strict=True)
        self.complete.to(self.device).eval()
        self.reset()

    def reset(self,camera=None):
        if camera is None:self.histories.clear();self.timestamps.clear()
        else:self.histories.pop(camera,None);self.timestamps.pop(camera,None)

    def infer(self,camera,frame,timestamp):
        try:return self._infer(camera,frame,timestamp)
        except Exception as exc:
            self.reset(camera)
            if self.device!='cuda':raise
            # All histories belong to the old device/model instance.
            log.exception('GPU inference failed; reload on CPU')
            self.device='cpu';self.fallback_reason=f'GPU inference failed: {exc}'
            self._load()
            return self._infer(camera,frame,timestamp)

    def _infer(self,camera,frame,timestamp):
        import cv2
        import numpy as np
        torch=self.torch
        previous=self.timestamps.get(camera)
        if previous is not None and (timestamp<=previous or timestamp-previous>self.settings.max_frame_gap):self.reset(camera)
        rgb=cv2.cvtColor(frame,cv2.COLOR_BGR2RGB)
        x=torch.from_numpy(cv2.resize(rgb,(640,640)).astype(np.float32)/255).permute(2,0,1).unsqueeze(0).to(self.device)
        with torch.inference_mode():
            temporal=self.complete.infer_frame(x,self.histories.setdefault(camera,[]))
            result=self.yolo(frame,verbose=False,device=self.device,conf=self.settings.yolo_confidence)[0]
        self.timestamps[camera]=timestamp
        detections=[]
        if result.boxes is not None:
            for box in result.boxes:
                detections.append(dict(label=result.names[int(box.cls[0])],confidence=float(box.conf[0]),bbox=[int(v) for v in box.xyxy[0].tolist()]))
        decision=decide(temporal['class_probabilities'],detections,self.settings.defect_threshold)
        return dict(**decision,detections=detections,probabilities=temporal['class_probabilities'],ae_error=temporal['ae_error'],history_size=temporal['history_size'],model_version=self.manifest['version'])
