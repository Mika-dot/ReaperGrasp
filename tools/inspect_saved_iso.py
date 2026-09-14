"""Boot the actual ISO through its bootloader, without network or host cameras."""
import argparse,json,socket,subprocess,tempfile,time
from pathlib import Path
from PIL import Image

def main():
    p=argparse.ArgumentParser();p.add_argument('image',type=Path);p.add_argument('output',type=Path);p.add_argument('--timeout',type=int,default=360);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        monitor=Path(tmp)/'monitor';serial=a.output/'boot-serial.log';screen=a.output/'boot.ppm'
        with (a.output/'qemu.log').open('w') as log:
            vm=subprocess.Popen(['qemu-system-x86_64','-accel','tcg','-cpu','max','-smp','2','-m','4096','-cdrom',str(a.image),'-boot','d','-vga','virtio','-display','none','-nic','none','-serial',f'file:{serial}','-qmp',f'unix:{monitor},server=on,wait=off'],stdout=log,stderr=log)
            try:
                deadline=time.monotonic()+a.timeout;gui=False;ready=False
                while time.monotonic()<deadline and vm.poll() is None:
                    time.sleep(10)
                    if serial.exists():ready='REAPERGRASP_BOOT_OK' in serial.read_text(errors='replace')
                    if not monitor.exists():continue
                    with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as sock:
                        sock.settimeout(10);sock.connect(str(monitor))
                        reader=sock.makefile('rb');json.loads(reader.readline())
                        for command in [{'execute':'qmp_capabilities'},{'execute':'screendump','arguments':{'filename':str(screen.resolve())}}]:
                            sock.sendall((json.dumps(command)+'\n').encode())
                            while True:
                                reply=json.loads(reader.readline())
                                if 'error' in reply:raise RuntimeError(reply)
                                if 'return' in reply:break
                        reader.close()
                    if screen.exists():
                        try:
                            Image.open(screen).save(a.output/'boot.png')
                            text=subprocess.check_output(['tesseract',str(a.output/'boot.png'),'stdout'],stderr=subprocess.DEVNULL).decode(errors='replace')
                            gui='reapergrasp' in text.lower().replace(' ','');print('SCREEN:',text[-1600:],flush=True)
                        except (OSError,subprocess.CalledProcessError):pass
                    if ready and gui:break
                report={'backend_ready':ready,'gui_visible':gui,'network':'disabled','acceleration':'TCG','physical_hardware_tested':False}
                (a.output/'boot-result.json').write_text(json.dumps(report,indent=2));print(report)
                print(serial.read_text(errors='replace')[-12000:] if serial.exists() else 'No serial log')
                assert ready and gui,'Boot verification failed; inspect boot.png and serial log'
            finally:
                vm.terminate()
                try:vm.wait(timeout=10)
                except subprocess.TimeoutExpired:vm.kill();vm.wait()
if __name__=='__main__':main()
