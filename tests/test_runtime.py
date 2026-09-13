import json
import pytest
from reapergrasp.decision import decide
from reapergrasp.settings import Settings,save,load
from reapergrasp.storage import EventStore
from reapergrasp.model import choose_device,verify_bundle

def test_warmup_not_normal():assert decide(None,[])['state']=='warming_up'
def test_disagreement_not_normal():assert decide([.1,.1,.1,.2,.5],[{'label':'foreign'}])['state']=='review'
def test_normal():assert decide([.01,.01,.01,.01,.96],[])['state']=='normal'
def test_defect():assert decide([.05,.8,.05,.05,.05],[])['state']=='defect'
def test_invalid_probability():
    with pytest.raises(ValueError):decide([float('nan')]*5,[])
def test_atomic_config(tmp_path):
    p=tmp_path/'settings.json';save(p,Settings());assert load(p).source=='auto'
    p.write_text('{bad')
    with pytest.raises(ValueError):load(p)
def test_journal_restart_and_retention(tmp_path):
    settings=Settings(max_events=2,min_free_mb=16);store=EventStore(tmp_path,settings)
    for n in range(3):store.record('c',{'state':'review','n':n},b'jpeg'+bytes([n]))
    store=EventStore(tmp_path,settings);assert len(store.list())==2
    row=store.list()[0];assert store.image(row['id'])==b'jpeg\x02'
def test_journal_rejects_nonfinite_atomically(tmp_path):
    store=EventStore(tmp_path,Settings(min_free_mb=16))
    with pytest.raises(ValueError):store.record('c',{'state':'review','p':float('nan')},b'jpeg')
    assert store.list()==[]
def test_cuda_probe_failure():
    class Cuda:
        @staticmethod
        def is_available():return True
    class Torch:
        cuda=Cuda()
        @staticmethod
        def ones(*args,**kwargs):raise RuntimeError('driver failure')
    device,reason=choose_device(Torch());assert device=='cpu' and 'driver failure' in reason

def test_manifest_tampering(tmp_path):
    (tmp_path/'manifest.json').write_text(json.dumps({'seq_length':16,'classes':['connection','foreign','garbage','point','normal'],'sha256':{'yolo.pt':'bad'}}))
    (tmp_path/'yolo.pt').write_bytes(b'bad')
    with pytest.raises(ValueError,match='checksum'):verify_bundle(tmp_path)

def test_disk_full_never_claims_recorded(tmp_path,monkeypatch):
    import reapergrasp.storage as storage
    from types import SimpleNamespace
    store=EventStore(tmp_path,Settings(min_free_mb=16))
    monkeypatch.setattr(storage.shutil,'disk_usage',lambda path:SimpleNamespace(free=0))
    with pytest.raises(OSError):store.record('c',{'state':'defect'},b'jpeg')
    assert store.list()==[]
