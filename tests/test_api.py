from fastapi.testclient import TestClient
from reapergrasp.__main__ import create_app
from reapergrasp.service import Service
from reapergrasp.settings import Settings

def test_origin_and_settings_validation(tmp_path):
    service=Service(Settings(),tmp_path);client=TestClient(create_app(service))
    assert client.get('/').status_code==200
    assert client.post('/api/settings',json={'capture_fps':3}).status_code==403
    assert client.post('/api/settings',json={'capture_fps':'oops'},headers={'origin':'http://testserver'}).status_code==400
    assert client.post('/api/settings',json={'capture_fps':3},headers={'origin':'http://testserver'}).status_code==200
    assert service.commands.get_nowait().capture_fps==3

def test_stale_not_normal(tmp_path):
    from types import SimpleNamespace
    service=Service(Settings(),tmp_path);service.cameras={'a':SimpleNamespace(state={'state':'normal','probability':.01,'processed':0})}
    assert service.snapshot()['cameras'][0]['state']=='stale'
