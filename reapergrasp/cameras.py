import hashlib
import multiprocessing as mp
import queue
import re
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit


@dataclass(frozen=True)
class Source:
    id: str
    path: str
    label: str
    demo: bool=False


def discover(settings):
    if settings.source=='demo':
        root=Path(settings.demo_dir)
        return [Source('demo-'+p.name,str(p),p.name,True) for p in sorted(root.glob('camera_*')) if p.is_dir()]
    paths=list(settings.cameras)
    if not paths:
        paths=[str(p) for p in sorted(Path('/dev/v4l/by-id').glob('*video-index0'))]
        if not paths:paths=[str(p) for p in sorted(Path('/dev').glob('video[0-9]*'))]
    seen=set();sources=[]
    for path in paths:
        resolved=str(Path(path).resolve()) if '://' not in path else path
        if resolved in seen:continue
        seen.add(resolved)
        label=(urlsplit(path).hostname or 'IP camera') if '://' in path else Path(path).name
        sources.append(Source(hashlib.sha256(path.encode()).hexdigest()[:12],path,label))
    return sources


def natural(path):
    return [int(x) if x.isdigit() else x.lower() for x in re.split(r'(\d+)',path.name)]


def capture_process(source,output,stop,fps):
    import cv2
    cv2.setNumThreads(1)
    index=0;epoch=0;cap=None
    try:
        if source.demo:
            paths=sorted([p for p in Path(source.path).iterdir() if p.suffix.lower() in {'.jpg','.png','.jpeg'}],key=natural)
            if not paths:raise FileNotFoundError('Нет кадров демонстрации')
        else:
            if '://' in source.path:
                cap=cv2.VideoCapture(source.path,cv2.CAP_FFMPEG,[cv2.CAP_PROP_OPEN_TIMEOUT_MSEC,3000,cv2.CAP_PROP_READ_TIMEOUT_MSEC,2000])
            else:
                cap=cv2.VideoCapture(source.path,cv2.CAP_V4L2)
                cap.set(cv2.CAP_PROP_BUFFERSIZE,1)
                cap.set(cv2.CAP_PROP_FPS,fps)
            if not cap.isOpened():raise RuntimeError('Не удалось открыть камеру')
        while not stop.is_set():
            start=time.monotonic()
            if source.demo:
                if index and index%len(paths)==0:epoch+=1
                encoded=paths[index%len(paths)].read_bytes();ok=bool(encoded)
            else:
                ok,frame=cap.read()
                if ok:
                    ok,buffer=cv2.imencode('.jpg',frame,[cv2.IMWRITE_JPEG_QUALITY,95])
                    if ok:encoded=buffer.tobytes()
            if not ok:raise RuntimeError('Камера перестала отдавать кадры')
            packet=dict(index=index,epoch=epoch,captured=start,encoded=encoded)
            try:output.put_nowait(packet)
            except queue.Full:pass  # Sequence numbers expose every lost frame to inference.
            index+=1
            stop.wait(max(0,1/fps-(time.monotonic()-start)))
    except Exception as exc:
        try:output.put(dict(error=str(exc)),timeout=.2)
        except queue.Full:pass
    finally:
        if cap is not None:cap.release()
        output.cancel_join_thread()


class Camera:
    def __init__(self,source,settings):
        self.source=source;self.settings=settings
        self.ctx=mp.get_context('spawn');self.process=None;self.output=None;self.stop_event=None
        self.last_packet=None;self.last_index=None;self.epoch=None;self.dropped=0
        self.started=0;self.retry_at=0
        self.state=dict(id=source.id,label=source.label,state='connecting',probability=None,history_size=0)
        self.jpeg=None

    def start(self):
        self.stop()
        self.output=self.ctx.Queue(self.settings.queue_size);self.stop_event=self.ctx.Event()
        self.process=self.ctx.Process(target=capture_process,args=(self.source,self.output,self.stop_event,self.settings.capture_fps),daemon=True)
        self.process.start();self.started=time.monotonic();self.last_packet=None;self.last_index=None;self.epoch=None
        self.state.update(state='connecting',error=None)

    def stop(self):
        if self.process is not None:
            self.stop_event.set();self.process.join(timeout=1)
            if self.process.is_alive():self.process.terminate();self.process.join(timeout=2)
            if self.process.is_alive():self.process.kill();self.process.join(timeout=2)
            if self.process.is_alive():raise RuntimeError('Capture process could not stop')
            self.process.close();self.process=None
        if self.output is not None:self.output.close();self.output=None

    def fail(self,message):
        self.stop();self.retry_at=time.monotonic()+3
        self.jpeg=None;self.state.update(state='camera_error',error=message,history_size=0,probability=None)

    def poll(self):
        now=time.monotonic()
        if self.process is None:
            if now>=self.retry_at:self.start()
            return None
        try:packet=self.output.get_nowait()
        except queue.Empty:
            if not self.process.is_alive() or now-(self.last_packet or self.started)>max(10,self.settings.stale_seconds*2):self.fail('Тайм-аут камеры; переподключение')
            return None
        if 'error' in packet:self.fail(packet['error']);return None
        gap=(self.last_index is not None and packet['index']!=self.last_index+1)
        if gap:self.dropped+=max(0,packet['index']-self.last_index-1)
        packet['reset']=self.last_index is None or gap or (self.epoch is not None and self.epoch!=packet['epoch'])
        self.last_index=packet['index'];self.epoch=packet['epoch'];self.last_packet=now
        self.state['dropped']=self.dropped
        return packet
