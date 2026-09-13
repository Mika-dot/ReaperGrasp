"""systemd watchdog: a responsive web server alone is not evidence of inference health."""
import os
import socket
import threading
import time

def start(service):
    address=os.getenv('NOTIFY_SOCKET');period=int(os.getenv('WATCHDOG_USEC','0'))/1e6
    if not address or not period:return
    if address.startswith('@'):address='\0'+address[1:]
    def run():
        while not service.stop_event.wait(min(10,period/4)):
            if time.monotonic()-service.heartbeat>period/2:continue
            try:
                with socket.socket(socket.AF_UNIX,socket.SOCK_DGRAM) as sock:
                    sock.connect(address);sock.sendall(b'WATCHDOG=1')
            except OSError:pass
    threading.Thread(target=run,daemon=True).start()
