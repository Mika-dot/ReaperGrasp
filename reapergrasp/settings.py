import math
import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@dataclass
class Settings:
    source: str = 'auto'
    device: str = 'auto'
    model_dir: str = str(ROOT / 'models/version_1')
    demo_dir: str = str(ROOT / 'examples/replay')
    cameras: list[str] = field(default_factory=list)
    rois: dict = field(default_factory=dict)
    defect_threshold: float = .7
    yolo_confidence: float = .25
    max_frame_gap: float = 2.0
    stale_seconds: float = 3.0
    capture_fps: float = 2.0
    queue_size: int = 4
    threads: int = 2
    retention_days: int = 30
    max_events: int = 10000
    min_free_mb: int = 256

    def validate(self):
        for name in ('capture_fps','max_frame_gap','stale_seconds','defect_threshold','yolo_confidence'):
            value=getattr(self,name)
            if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):raise ValueError(f'Invalid {name}')
        for name in ('queue_size','threads','retention_days','max_events','min_free_mb'):
            if type(getattr(self,name)) is not int:raise ValueError(f'Invalid {name}')
        if not isinstance(self.cameras,list) or any(not isinstance(p,str) or not (p.startswith('/dev/video') or p.startswith('/dev/v4l/') or p.startswith('rtsp://') or p.startswith('rtsps://')) for p in self.cameras):raise ValueError('Expected USB device paths or RTSP URLs')
        if not isinstance(self.rois,dict):raise ValueError('ROI must be an object')

        if self.source not in ('auto','demo') or self.device not in ('auto','cpu','cuda'):
            raise ValueError('Invalid source/device')
        if not .01 <= self.defect_threshold <= .99 or not .01 <= self.yolo_confidence <= .99:
            raise ValueError('Threshold must be within 0.01..0.99')
        if not 1 <= self.queue_size <= 256 or not 1 <= self.threads <= 64:
            raise ValueError('Invalid queue size or thread count')
        if not 1 <= self.capture_fps <= 240 or not .1 <= self.max_frame_gap <= 60:
            raise ValueError('Invalid frame rate or maximum gap')
        if not .5 <= self.stale_seconds <= 120 or not 1 <= self.retention_days <= 3650 or not 1 <= self.max_events <= 1000000 or self.min_free_mb < 16:
            raise ValueError('Invalid retention/stale/disk settings')
        for camera, roi in self.rois.items():
            if not isinstance(roi,list) or len(roi)!=4 or any(not isinstance(v,int) or v<0 for v in roi) or roi[2]<1 or roi[3]<1:
                raise ValueError(f'Invalid ROI for {camera}')
        return self


def state_dir():
    root = Path(os.getenv('REAPERGRASP_STATE_DIR', str(Path.home()/'.local/share/reapergrasp')))
    root.mkdir(parents=True, exist_ok=True)
    return root


def save(path, settings):
    settings.validate()
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    fd,name=tempfile.mkstemp(prefix=path.name+'.',dir=path.parent)
    try:
        with os.fdopen(fd,'w') as f:
            json.dump(asdict(settings),f,ensure_ascii=False,indent=2);f.flush();os.fsync(f.fileno())
        os.replace(name,path)
        directory_fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
        try:os.fsync(directory_fd)
        finally:os.close(directory_fd)
    finally:
        if os.path.exists(name):os.unlink(name)


def load(path):
    path=Path(path)
    if not path.exists():
        settings=Settings();save(path,settings);return settings
    # A corrupt configuration is an explicit startup error, never silent defaults.
    return Settings(**json.loads(path.read_text())).validate()
