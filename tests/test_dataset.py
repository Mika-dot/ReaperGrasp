import json
import pytest
from dataset import index_manifest

def make(tmp_path):
    records=[]
    for split in ('train','val'):
        frames=[]
        for i in range(16):
            p=tmp_path/f'{split}{i}.jpg';p.write_bytes(f'{split}-{i}'.encode());frames.append({'index':i,'path':p.name})
        records.append(dict(split=split,group=split,label=4,frames=frames))
    return records

def test_group_isolation(tmp_path):
    r=make(tmp_path);p=tmp_path/'recordings.json';p.write_text(json.dumps(r));assert len(index_manifest(p)['train'])==1
    r[1]['group']='train';p.write_text(json.dumps(r))
    with pytest.raises(ValueError,match='group leaks'):index_manifest(p)
def test_duplicate_content_isolation(tmp_path):
    r=make(tmp_path);(tmp_path/'val0.jpg').write_bytes((tmp_path/'train0.jpg').read_bytes());p=tmp_path/'recordings.json';p.write_text(json.dumps(r))
    with pytest.raises(ValueError,match='Duplicate frame'):index_manifest(p)
def test_missing_frame_rejects_window(tmp_path):
    r=make(tmp_path);r[1]['frames'][-1]['index']=17;p=tmp_path/'recordings.json';p.write_text(json.dumps(r))
    with pytest.raises(ValueError,match='complete windows'):index_manifest(p)
