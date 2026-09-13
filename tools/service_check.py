"""Exercise the real service, capture subprocesses, HTTP API, journal and shutdown."""
import json,sys,tempfile,time,multiprocessing
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from reapergrasp.__main__ import create_app
from reapergrasp.service import Service
from reapergrasp.settings import Settings

def main():
    with tempfile.TemporaryDirectory() as directory:
        service=Service(Settings(source='demo',device='cpu',min_free_mb=16),Path(directory));seen={}
        with TestClient(create_app(service)) as client:
            deadline=time.monotonic()+60
            while time.monotonic()<deadline:
                state=client.get('/api/status').json()
                assert state['status']!='error',state
                for camera in state['cameras']:
                    if camera['history_size']==16:
                        seen[camera['id']]=camera
                        image=client.get('/api/frame/'+camera['id']);assert image.status_code==200 and image.content.startswith(b'\xff\xd8')
                if len(seen)==2 and len(client.get('/api/events').json())>=2:break
                time.sleep(.1)
            assert len(seen)==2,state
            events=client.get('/api/events').json();assert len(events)>=2
            assert {c['state'] for c in seen.values()}=={'defect','review'}
        assert not service.thread.is_alive()
        assert not multiprocessing.active_children()
        report={'cameras':seen,'events':len(events),'clean_shutdown':True}
        Path('docs/validation-service.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
if __name__=='__main__':main()
