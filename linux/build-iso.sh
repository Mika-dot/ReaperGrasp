#!/bin/bash
# Build on a privileged Debian 12 amd64 host with live-build installed.
set -euo pipefail
[[ $EUID == 0 ]] || { echo 'Root with mount/chroot capabilities is required'; exit 1; }
command -v lb >/dev/null
source_dir=$(cd "$(dirname "$0")/.." && pwd)
build_dir=${REAPERGRASP_BUILD_DIR:-/var/tmp/reapergrasp-live}
mkdir -p "$build_dir"
cd "$build_dir"
lb config --distribution bookworm --architectures amd64 --binary-images iso-hybrid --archive-areas 'main contrib non-free non-free-firmware' --debian-installer live --bootappend-live 'boot=live components persistence quiet username=operator'
mkdir -p config/includes.chroot/opt/reapergrasp config/hooks/normal config/package-lists
rsync -a --exclude=.git --exclude=.venv --exclude=build "$source_dir/" config/includes.chroot/opt/reapergrasp/
printf 'linux-image-amd64\nlive-boot\nlive-config\nsystemd-sysv\nfirmware-linux\npython3-venv\npython3-pip\ncage\nchromium\nrsync\n' > config/package-lists/reapergrasp.list.chroot
cat > config/hooks/normal/0900-reapergrasp.hook.chroot <<'HOOK'
#!/bin/sh
set -eu
bash /opt/reapergrasp/linux/install.sh --kiosk cpu
# No desktop, remote shell, or password login in appliance mode.
passwd -l root
HOOK
chmod +x config/hooks/normal/0900-reapergrasp.hook.chroot
lb build
sha256sum live-image-amd64.hybrid.iso > live-image-amd64.hybrid.iso.sha256
