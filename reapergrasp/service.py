import queue
import copy
import logging
import threading
import time
from .cameras import Camera, discover
from .model import ModelEngine
from .storage import EventStore

class Service:
    def __init__(self, settings, root, startup_error=None):
        self.heartbeat=time.monotonic();self.settings=settings;self.root=root;self.cameras={};self.engine=None
        self.startup_error=startup_error;self.status='starting';self.error=None;self.storage_error=None
        self.commands=queue.Queue(maxsize=1);self.lock=threading.RLock();self.stop_event=threading.Event();self.last_events={}
        self.store=None
        self.thread=threading.Thread(target=self.run,daemon=True)
    def start(self):
        from .watchdog import start
        self.thread.start();start(self)
    def stop(self):
        self.stop_event.set();self.thread.join(timeout=30)
        if self.thread.is_alive():raise RuntimeError('Inference did not stop')
    def snapshot(self):
        with self.lock:
            rows=copy.deepcopy([c.state for c in self.cameras.values()])
            for row in rows:
                if time.monotonic()-row.get('processed',0)>self.settings.stale_seconds and row['state'] in ('normal','defect','review','warming_up'):
                    row.update(state='stale',probability=None)
            return dict(status=self.status,error=self.error,storage_error=self.storage_error,source=self.settings.source,device=self.engine.device if self.engine else None,fallback_reason=self.engine.fallback_reason if self.engine else None,cameras=rows)
    def frame(self,camera):
        with self.lock:
            c=self.cameras.get(camera);return c.jpeg if c else None
    def run(self):
        while not self.stop_event.is_set():
            self.heartbeat=time.monotonic();self._run_once()
            if self.stop_event.wait(5):break
            try:
                self.settings=self.commands.get_nowait();self.startup_error=None
            except queue.Empty:pass
    def _run_once(self):
        try:
            if self.startup_error:raise ValueError(self.startup_error)
            import cv2
            import numpy as np
            cv2.setNumThreads(1)
            self.store=EventStore(self.root,self.settings)
            self.engine=ModelEngine(self.settings);self.status='running';self.error=None;scanned=0
            while not self.stop_event.is_set():
                try:
                    settings=self.commands.get_nowait()
                except queue.Empty:settings=None
                if settings is not None:
                    with self.lock:
                        for camera in self.cameras.values():camera.stop()
                        self.cameras.clear();self.settings=settings;self.store.settings=settings
                        self.engine=ModelEngine(settings);scanned=0
                now=time.monotonic();self.heartbeat=now
                if now-scanned>3:
                    sources={s.id:s for s in discover(self.settings)}
                    with self.lock:
                        for key in list(self.cameras):
                            if key not in sources:self.cameras.pop(key).stop();self.engine.reset(key)
                        for key,source in sources.items():
                            if key not in self.cameras:self.cameras[key]=Camera(source,self.settings)
                    scanned=now
                active=False
                for key,camera in list(self.cameras.items()):
                    if self.stop_event.is_set():break
                    packet=camera.poll()
                    if packet is None:continue
                    active=True
                    if packet['reset']:self.engine.reset(key)
                    if time.monotonic()-packet['captured']>self.settings.stale_seconds:
                        self.engine.reset(key)
                        with self.lock:camera.state.update(state='overloaded',probability=None,history_size=0)
                        continue
                    try:
                        frame=cv2.imdecode(np.frombuffer(packet['encoded'],dtype=np.uint8),cv2.IMREAD_COLOR)
                        if frame is None:raise ValueError('Invalid camera image')
                        roi=self.settings.rois.get(key)
                        if roi:
                            x,y,w,h=roi
                            if x+w>frame.shape[1] or y+h>frame.shape[0]:raise ValueError('ROI outside camera frame')
                            frame=frame[y:y+h,x:x+w]
                        result=self.engine.infer(key,frame,packet['captured'])
                        for box in result['detections']:
                            x,y,x2,y2=box['bbox'];cv2.rectangle(frame,(x,y),(x2,y2),(0,180,255),2)
                        ok,jpeg=cv2.imencode('.jpg',frame,[cv2.IMWRITE_JPEG_QUALITY,80])
                        if not ok:raise RuntimeError('JPEG encoding failed')
                        image=jpeg.tobytes()
                        if time.monotonic()-packet['captured']>self.settings.stale_seconds:
                            result.update(state='stale',probability=None)
                        with self.lock:
                            camera.jpeg=image;camera.state.update(result,processed=time.monotonic(),error=None);camera.state['temporal_label']=result['label'];camera.state['label']=camera.source.label
                        if result['state'] in ('defect','review') and now-self.last_events.get(key,0)>2:
                            try:
                                self.store.record(key,result,image);self.last_events[key]=now;self.storage_error=None
                            except Exception as exc:self.storage_error=str(exc)
                    except Exception as exc:
                        self.engine.reset(key)
                        with self.lock:camera.state.update(state='inference_error',error=str(exc),probability=None,history_size=0)
                if not active:self.stop_event.wait(.01)
        except Exception as exc:
            logging.exception('Service failed');self.status='error';self.error=str(exc)
        finally:
            with self.lock:
                for camera in self.cameras.values():camera.stop()
                self.cameras.clear()
