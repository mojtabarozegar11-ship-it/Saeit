#!/usr/bin/env bash
# Safe, independent ComfyUI bootstrap. Run deliberately on VPS as root only after preflight.
set -Eeuo pipefail
if [[ "${EUID}" -ne 0 ]]; then echo "Run as root"; exit 1; fi
if [[ "${CONFIRM_COMFYUI_INSTALL:-}" != "YES" ]]; then
  echo "Refusing to install: set CONFIRM_COMFYUI_INSTALL=YES after reviewing preflight."; exit 2
fi
command -v python3 >/dev/null || { echo "python3 missing"; exit 3; }
command -v git >/dev/null || { echo "git missing"; exit 3; }
if ss -ltn '( sport = :8188 )' | grep -q LISTEN; then
  echo "Port 8188 already in use: refusing to modify existing services"; exit 4
fi
if id comfyui-svc &>/dev/null || [[ -e /opt/comfyui-isolated ]]; then
  echo "Existing service/path detected: refusing replacement"; exit 5
fi
useradd --system --home /opt/comfyui-isolated --shell /usr/sbin/nologin comfyui-svc
install -d -m 0750 -o comfyui-svc -g comfyui-svc /opt/comfyui-isolated
git clone --depth 1 https://github.com/comfyanonymous/ComfyUI.git /opt/comfyui-isolated/ComfyUI
python3 -m venv /opt/comfyui-isolated/venv
/opt/comfyui-isolated/venv/bin/pip install --upgrade pip
# CPU-only default; GPU-specific torch wheels must be planned from verified host resources.
# Pin deployed dependency revisions in production after compatibility testing.
/opt/comfyui-isolated/venv/bin/pip install torch --index-url https://download.pytorch.org/whl/cpu
/opt/comfyui-isolated/venv/bin/pip install -r /opt/comfyui-isolated/ComfyUI/requirements.txt
chown -R comfyui-svc:comfyui-svc /opt/comfyui-isolated
install -m 0644 "$(dirname "$0")/comfyui-isolated.service" /etc/systemd/system/comfyui-isolated.service
systemctl daemon-reload
# Explicit start only: no enable and no external port / reverse proxy changes.
echo "Installed. Start explicitly with: systemctl start comfyui-isolated"
echo "Bind address: 127.0.0.1:8188; access through a separately secured tunnel."
