import queue,time
from reapergrasp.cameras import Camera,Source
from reapergrasp.settings import Settings

class Process:
    def is_alive(self):return True

def test_camera_restart_gap_and_epoch_reset():
    camera=Camera(Source('c','/dev/video0','camera'),Settings())
    camera.process=Process();camera.output=queue.Queue();camera.started=time.monotonic()
    for index,epoch,expected in [(0,0,True),(1,0,False),(4,0,True),(5,1,True)]:
        camera.output.put(dict(index=index,epoch=epoch))
        assert camera.poll()['reset']==expected
    assert camera.dropped==2

def test_dead_camera_is_not_normal():
    camera=Camera(Source('c','/dev/video0','camera'),Settings())
    camera.process=Process();camera.output=queue.Queue();camera.started=time.monotonic()-30
    camera.stop=lambda:None
    camera.poll();assert camera.state['state']=='camera_error' and camera.state['probability'] is None
