#!/usr/bin/env bash
# Install on the hosting account only, never on Production or the VPS.
set -euo pipefail
: "${VPS_HOST:=178.239.147.150}"
: "${VPS_USER:=githubops}"
: "${VPS_PORT:=22}"
: "${REMOTE_PORT:=22222}"
: "${HOST_SSH_PORT:=22}"
: "${HOST_SSH_HOST:=127.0.0.1}"
: "${VPS_HOST_RSA_FINGERPRINT:=SHA256:AYdzF3K5uSwAXElE1w/dKo04iT2BbMGwHbRA2Cu4rrs}"
INSTALL_DIR="${HOME}/.zomorod-staging-tunnel"
umask 077
mkdir -p "$INSTALL_DIR"
if [[ ! -f "$INSTALL_DIR/id_ed25519" ]]; then
  ssh-keygen -q -t ed25519 -N '' -f "$INSTALL_DIR/id_ed25519" -C 'zomorod-staging-reverse-tunnel'
fi
ssh-keyscan -T 10 -p "$VPS_PORT" -t rsa "$VPS_HOST" 2>/dev/null > "$INSTALL_DIR/known_hosts.tmp"
test -s "$INSTALL_DIR/known_hosts.tmp" || { echo "VPS keyscan failed"; exit 1; }
observed="$(ssh-keygen -lf "$INSTALL_DIR/known_hosts.tmp" -E sha256 | awk 'NR==1{print $2}')"
test "$observed" = "$VPS_HOST_RSA_FINGERPRINT" || { echo "VPS host identity mismatch; aborting"; exit 1; }
mv "$INSTALL_DIR/known_hosts.tmp" "$INSTALL_DIR/known_hosts"
chmod 600 "$INSTALL_DIR/known_hosts"
cat > "$INSTALL_DIR/run.sh" <<EOF
#!/usr/bin/env bash
exec ssh -F /dev/null -N -T -i "$INSTALL_DIR/id_ed25519" \
  -o IdentitiesOnly=yes -o BatchMode=yes -o ExitOnForwardFailure=yes \
  -o ServerAliveInterval=30 -o ServerAliveCountMax=3 \
  -o StrictHostKeyChecking=yes -o UserKnownHostsFile="$INSTALL_DIR/known_hosts" \
  -p "$VPS_PORT" -R "127.0.0.1:$REMOTE_PORT:$HOST_SSH_HOST:$HOST_SSH_PORT" \
  "$VPS_USER@$VPS_HOST"
EOF
chmod 700 "$INSTALL_DIR/run.sh"
echo "PUBLIC KEY FOR VPS githubops authorized_keys (NOT A SECRET):"
cat "$INSTALL_DIR/id_ed25519.pub"
echo "Install key on VPS first, then run $INSTALL_DIR/run.sh on hosting."
echo "Tunnel exposes hosting SSH only on VPS loopback 127.0.0.1:$REMOTE_PORT."
