import argparse
import fcntl
from contextlib import asynccontextmanager
from pathlib import Path
import queue
from fastapi import FastAPI, HTTPException, Request
from dataclasses import asdict
from fastapi.responses import FileResponse, Response
from .settings import load, save, Settings, state_dir
from .service import Service

def create_app(service):
    @asynccontextmanager
    async def lifespan(app):
        service.start()
        try:yield
        finally:service.stop()
    app=FastAPI(lifespan=lifespan)
    @app.get('/')
    def index():return FileResponse(Path(__file__).parent/'static/index.html')
    @app.get('/api/settings')
    def settings():
        value=asdict(service.settings)
        return {k:value[k] for k in ('source','device','capture_fps','defect_threshold','yolo_confidence','cameras','rois')}
    @app.post('/api/settings')
    async def update_settings(request:Request):
        if request.headers.get('origin') != str(request.base_url).rstrip('/'):
            raise HTTPException(403,'Same-origin request required')
        if service.commands.full():raise HTTPException(409,'Previous change is still pending')
        try:
            changes=await request.json()
            allowed={'source','device','capture_fps','defect_threshold','yolo_confidence','cameras','rois'}
            if not isinstance(changes,dict) or set(changes)-allowed:raise ValueError('Unsupported settings')
            updated=Settings(**(asdict(service.settings)|changes)).validate()
            save(service.root/'settings.json',updated);service.commands.put_nowait(updated)
            return {'status':'queued'}
        except (ValueError,TypeError,AttributeError,queue.Full) as exc:raise HTTPException(400,str(exc))
    @app.get('/api/status')
    def status():return service.snapshot()
    @app.get('/api/events')
    def events():
        if service.store is None:raise HTTPException(503,'Journal unavailable')
        return service.store.list()
    @app.get('/api/frame/{camera}')
    def frame(camera:str):
        data=service.frame(camera)
        if data is None:raise HTTPException(404)
        return Response(data,media_type='image/jpeg',headers={'Cache-Control':'no-store'})
    @app.get('/api/events/{event_id}/image')
    def event_image(event_id:int):
        if service.store is None:raise HTTPException(503,'Journal unavailable')
        data=service.store.image(event_id)
        if data is None:raise HTTPException(404)
        return Response(data,media_type='image/jpeg')
    return app

def main():
    import uvicorn
    parser=argparse.ArgumentParser();parser.add_argument('--demo',action='store_true');parser.add_argument('--cpu',action='store_true');parser.add_argument('--port',type=int,default=8010)
    args=parser.parse_args();root=state_dir()
    with (root/'instance.lock').open('w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        startup_error=None
        try:settings=load(root/'settings.json')
        except (ValueError,TypeError,OSError) as exc:
            settings=Settings();startup_error=f'Configuration error: {exc}'
        if args.demo:settings.source='demo'
        if args.cpu:settings.device='cpu'
        uvicorn.run(create_app(Service(settings,root,startup_error)),host='127.0.0.1',port=args.port)
if __name__=='__main__':main()
