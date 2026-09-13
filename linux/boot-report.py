"""Readiness report for the experimental image's serial console. No network required."""
import json,time,urllib.request
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
status={}
for _ in range(240):
    try:
        with opener.open('http://127.0.0.1:8010/api/status',timeout=2) as response:status=json.load(response)
        if status['status']=='running' and status['device'] in ('cpu','cuda'):
            with open('/dev/ttyS0','w') as serial:serial.write('REAPERGRASP_BOOT_OK '+json.dumps(status)+'\n');serial.flush()
            break
    except (OSError,ValueError):pass
    time.sleep(1)
else:
    with open('/dev/ttyS0','w') as serial:serial.write('REAPERGRASP_BOOT_FAILED '+json.dumps(status)+'\n')
    raise SystemExit(1)
