"""Real-weight smoke test. This does not measure classification accuracy."""
import json,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import cv2
from reapergrasp.model import ModelEngine
from reapergrasp.settings import Settings
from reapergrasp.cameras import natural

def main():
    engine=ModelEngine(Settings(device='cpu'));report=[]
    for folder in sorted(Path(engine.settings.demo_dir).glob('camera_*')):
        states=[];durations=[]
        for n,path in enumerate(sorted(folder.glob('*.jpg'),key=natural)):
            t=time.perf_counter();result=engine.infer(folder.name,cv2.imread(str(path)),n*.5+1);durations.append(time.perf_counter()-t);states.append(result['state'])
            assert result['history_size']==min(n+1,16)
            if n<15:assert result['state']=='warming_up'
        assert len(states)>=16 and states[15]!='warming_up'
        report.append(dict(camera=folder.name,frames=len(states),last=result,mean_seconds=sum(durations)/len(durations)))
        engine.reset(folder.name)
        assert engine.infer(folder.name,cv2.imread(str(path)),100)['state']=='warming_up'
    assert len(report)==2
    target=Path('docs/validation-replay.json');target.write_text(json.dumps(report,indent=2));print(target.read_text())
if __name__=='__main__':main()
