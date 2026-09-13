#!/bin/bash
# Dedicated Debian 12 amd64 appliance. Run on the target, never a workstation.
set -euo pipefail
if [[ $EUID != 0 ]]; then echo 'Run as root on the dedicated target'; exit 1; fi
if [[ ${1:-} != --kiosk ]]; then echo 'Usage: sudo bash linux/install.sh --kiosk [cpu|cuda]'; exit 1; fi
cd "$(dirname "$0")/.."
profile=${2:-cuda}
case "$profile" in cpu) torch_index=https://download.pytorch.org/whl/cpu;; cuda) torch_index=https://download.pytorch.org/whl/cu128;; *) exit 2;; esac
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y python3-venv python3-pip libgl1 libglib2.0-0 cage chromium dbus-user-session libpam-systemd v4l-utils rsync
getent group render >/dev/null || groupadd --system render
id reapergrasp >/dev/null 2>&1 || useradd --system --create-home --home-dir /var/lib/reapergrasp --shell /usr/sbin/nologin reapergrasp
usermod -a -G video,render,input reapergrasp
mkdir -p /opt/reapergrasp
if [[ $(pwd) != /opt/reapergrasp ]]; then rsync -a --exclude=.git --exclude=.venv --exclude=build ./ /opt/reapergrasp/; fi
cd /opt/reapergrasp
python3 tools/fetch_assets.py
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip==25.2
.venv/bin/pip install torch==2.8.0 torchvision==0.23.0 --index-url "$torch_index"
.venv/bin/pip install -r requirements.txt
.venv/bin/python -c 'from reapergrasp.model import verify_bundle; verify_bundle("models/version_1")'
install -m 644 linux/systemd/*.service /etc/systemd/system/
mkdir -p /etc/chromium/policies/managed
cat > /etc/chromium/policies/managed/reapergrasp.json <<'JSON'
{"DeveloperToolsAvailability":2,"BrowserGuestModeEnabled":false,"BrowserAddPersonEnabled":false,"BrowserSignin":0,"PasswordManagerEnabled":false,"DownloadRestrictions":3,"PrintingEnabled":false,"URLBlocklist":["*"],"URLAllowlist":["http://127.0.0.1:8010/*"]}
JSON
mkdir -p /etc/systemd/logind.conf.d
printf '[Login]\nNAutoVTs=0\nReserveVT=0\n' > /etc/systemd/logind.conf.d/reapergrasp.conf
systemctl mask getty@tty1.service getty@tty2.service getty@tty3.service getty@tty4.service getty@tty5.service getty@tty6.service ctrl-alt-del.target
systemctl set-default multi-user.target
systemctl enable reapergrasp.service reapergrasp-kiosk.service reapergrasp-boot-report.service
# During image construction systemd is not running. Start on next boot.
if [[ -d /run/systemd/system ]]; then systemctl daemon-reload;systemctl restart reapergrasp.service reapergrasp-kiosk.service; fi
