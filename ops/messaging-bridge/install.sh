#!/usr/bin/env bash
# Explicit installer. DOES NOT enable/start any service or touch factory/sites.
set -euo pipefail
[[ "$(id -u)" == 0 ]] || { echo 'Run with sudo'; exit 2; }
command -v python3 >/dev/null || { echo 'Python 3 is required'; exit 2; }
command -v npm >/dev/null || { echo 'Node.js 20+ and npm required'; exit 2; }
node -e 'process.exit(Number(process.versions.node.split(".")[0])>=20?0:1)' || { echo 'Node.js 20+ required'; exit 2; }
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
USER_NAME=mojmsg
if ! id "$USER_NAME" >/dev/null 2>&1; then
  useradd --system --home /var/lib/moj-messaging --shell /usr/sbin/nologin "$USER_NAME"
fi
install -d -m 0700 -o "$USER_NAME" -g "$USER_NAME" /var/lib/moj-messaging
install -d -m 0750 -o root -g "$USER_NAME" /opt/moj-messaging
install -d -m 0750 -o root -g "$USER_NAME" /etc/moj-messaging
for f in telegram.py whatsapp.mjs requirements.txt package.json control.sh; do
  install -m 0640 -o root -g "$USER_NAME" "$HERE/$f" "/opt/moj-messaging/$f"
done
chmod 0750 /opt/moj-messaging/control.sh
python3 -m venv /opt/moj-messaging/.venv
/opt/moj-messaging/.venv/bin/pip install --disable-pip-version-check --no-cache-dir -r /opt/moj-messaging/requirements.txt
(cd /opt/moj-messaging && npm install --omit=dev --no-fund --no-audit)
chown -R root:"$USER_NAME" /opt/moj-messaging
chmod -R o-rwx /opt/moj-messaging
if [[ ! -f /etc/moj-messaging/bridge.env ]]; then
  install -m 0640 -o root -g "$USER_NAME" "$HERE/bridge.env.example" /etc/moj-messaging/bridge.env
fi
install -m 0644 "$HERE/systemd/moj-telegram.service" /etc/systemd/system/moj-telegram.service
install -m 0644 "$HERE/systemd/moj-whatsapp@.service" /etc/systemd/system/moj-whatsapp@.service
systemctl daemon-reload
printf '%s\n' 'INSTALLED ONLY: no services started and no accounts linked.' \
  'Edit /etc/moj-messaging/bridge.env securely, pair using sudo /opt/moj-messaging/control.sh, then enable services.'