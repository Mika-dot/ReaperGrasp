"""Boot the actual ISO through its bootloader, without network or host cameras."""
import argparse,json,socket,subprocess,tempfile,time
from pathlib import Path
from PIL import Image

def main():
    p=argparse.ArgumentParser();p.add_argument('image',type=Path);p.add_argument('output',type=Path);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        monitor=Path(tmp)/'monitor';serial=a.output/'boot-serial.log';screen=a.output/'boot.ppm'
        with (a.output/'qemu.log').open('w') as log:
            vm=subprocess.Popen(['qemu-system-x86_64','-accel','tcg','-cpu','max','-smp','2','-m','4096','-cdrom',str(a.image),'-boot','d','-vga','virtio','-display','none','-nic','none','-serial',f'file:{serial}','-monitor',f'unix:{monitor},server=on,wait=off'],stdout=log,stderr=log)
            try:
                deadline=time.monotonic()+360;gui=False;ready=False
                while time.monotonic()<deadline and vm.poll() is None:
                    time.sleep(10)
                    if serial.exists():ready='REAPERGRASP_BOOT_OK' in serial.read_text(errors='replace')
                    if not monitor.exists():continue
                    with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as sock:
                        sock.settimeout(5);sock.connect(str(monitor));sock.recv(4096);sock.sendall(f'screendump {screen}\n'.encode());sock.recv(4096)
                    if screen.exists():
                        try:
                            Image.open(screen).save(a.output/'boot.png')
                            text=subprocess.check_output(['tesseract',str(a.output/'boot.png'),'stdout'],stderr=subprocess.DEVNULL).decode(errors='replace')
                            gui='reapergrasp' in text.lower().replace(' ','')
                        except (OSError,subprocess.CalledProcessError):pass
                    if ready and gui:break
                report={'backend_ready':ready,'gui_visible':gui,'network':'disabled','acceleration':'TCG','physical_hardware_tested':False}
                (a.output/'boot-result.json').write_text(json.dumps(report,indent=2));print(report)
                assert ready and gui,'Boot verification failed; inspect boot.png and serial log'
            finally:
                vm.terminate()
                try:vm.wait(timeout=10)
                except subprocess.TimeoutExpired:vm.kill();vm.wait()
if __name__=='__main__':main()
