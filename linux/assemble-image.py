"""Run beside the downloaded ISO parts and image-manifest.json (Windows or Linux)."""
import hashlib,json,os
from pathlib import Path
root=Path(__file__).resolve().parent
manifest=json.loads((root/'image-manifest.json').read_text())
target=root/'ReaperGrasp.iso';temporary=root/'ReaperGrasp.iso.part';digest=hashlib.sha256()
try:
    with temporary.open('wb') as output:
        for name in manifest['parts']:
            if Path(name).name!=name:raise ValueError('Invalid part name')
            with (root/name).open('rb') as source:
                while chunk:=source.read(1024*1024):output.write(chunk);digest.update(chunk)
        output.flush();os.fsync(output.fileno())
    if digest.hexdigest()!=manifest['sha256']:raise ValueError('Checksum mismatch; download the parts again')
    if target.exists():raise FileExistsError('ReaperGrasp.iso already exists; original file preserved')
    os.replace(temporary,target);print('Verified image:',target)
finally:temporary.unlink(missing_ok=True)
