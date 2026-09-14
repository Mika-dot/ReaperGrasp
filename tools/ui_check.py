"""Headless browser check against the real local application."""
import json,os,subprocess,sys,tempfile,time,urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
def main():
    with tempfile.TemporaryDirectory() as state:
        server=subprocess.Popen([sys.executable,'-m','reapergrasp','--demo','--cpu'],cwd=ROOT,env=os.environ|{'REAPERGRASP_STATE_DIR':state},stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        try:
            opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
            for _ in range(100):
                try:
                    with opener.open('http://127.0.0.1:8010/',timeout=1):break
                except OSError:time.sleep(.2)
            with sync_playwright() as p:
                browser=p.chromium.launch();page=browser.new_page(viewport={'width':1440,'height':1000});errors=[]
                page.on('pageerror',lambda error:errors.append(str(error)))
                page.goto('http://127.0.0.1:8010/');page.wait_for_selector('article img',timeout=45000);page.wait_for_timeout(12000)
                assert page.locator('article').count()==2
                assert page.locator('article img').evaluate_all('(images)=>images.every(i=>i.naturalWidth>0)')
                assert not page.evaluate('document.documentElement.scrollWidth > innerWidth')
                assert not errors,errors
                page.screenshot(path=str(ROOT/'docs/ui-desktop.png'),full_page=True)
                page.set_viewport_size({'width':800,'height':600})
                assert not page.evaluate('document.documentElement.scrollWidth > innerWidth')
                page.screenshot(path=str(ROOT/'docs/ui-small.png'),full_page=True)
                (ROOT/'docs/validation-ui.json').write_text(json.dumps({'errors':errors,'cameras':2,'viewport_checks':['1440x1000','800x600']},indent=2))
                page.route('**/api/status',lambda route:None)
                page.wait_for_function("document.querySelector('#cameras').children.length===0 && document.querySelector('#notice').textContent.includes('Нет связи')",timeout=6000)
                browser.close()
        finally:
            server.terminate()
            try:server.wait(timeout=40)
            except subprocess.TimeoutExpired:server.kill();server.wait();raise
if __name__=='__main__':main()
