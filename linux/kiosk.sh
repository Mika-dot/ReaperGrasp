#!/bin/sh
set -eu
python3 - <<'PY'
import time,urllib.request
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
while True:
    try:
        with opener.open('http://127.0.0.1:8010/',timeout=2) as response:
            if response.status==200:break
    except OSError:pass
    time.sleep(1)
PY
exec /usr/bin/cage -- /usr/bin/chromium --ozone-platform=wayland --kiosk --no-first-run --disable-session-crashed-bubble --noerrdialogs --user-data-dir=/var/lib/reapergrasp/chromium http://127.0.0.1:8010
