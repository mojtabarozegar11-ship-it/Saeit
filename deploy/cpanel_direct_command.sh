#!/usr/bin/env bash
set -euo pipefail

# Direct cPanel bridge. Read-only allowlist only.
# The runner reaches cPanel through the pinned VPS jump host.
operation="${1:-}"
case "$operation" in
  relay_preflight|cpanel_version|passenger_inventory|management_passenger_binding|cpanel_preflight|django_check|django_migrations|runtime_path_diagnostics|runtime_python_candidates|management_runtime_fingerprint|management_domain_docroot) ;;
  *) echo "CPANEL_DIRECT_OPERATION_DENIED" >&2; exit 64 ;;
esac

: "${VPS_KEY:?VPS_KEY is required}"
: "${HOST_KEY:?HOST_KEY is required}"

work="${RUNNER_TEMP}/saeit-cpanel-direct"
install -d -m 700 "$work"
cleanup() { rm -rf -- "$work"; }
trap cleanup EXIT

normalize_key() {
  local value="$1" destination="$2"
  printf '%s' "$value" | python3 -c 'import sys; s=sys.stdin.read(); s=s.replace("\r\n","\n").replace("\r","").replace("\\n","\n").rstrip()+"\n"; sys.stdout.write(s)' > "$destination"
  chmod 600 "$destination"
  ssh-keygen -y -P "" -f "$destination" >/dev/null
}
normalize_key "$VPS_KEY" "$work/vps.key"
normalize_key "$HOST_KEY" "$work/host.key"

echo "BRIDGE_STAGE=VPS_HOST_KEY" >&2
ssh-keyscan -T 10 -t rsa 178.239.147.150 > "$work/vps.known" 2>/dev/null
test "$(ssh-keygen -lf "$work/vps.known" -E sha256 | awk '{print $2}' | sort -u)" = "SHA256:AYdzF3K5uSwAXElE1w/dKo04iT2BbMGwHbRA2Cu4rrs"

echo "BRIDGE_STAGE=CPANEL_HOST_KEY" >&2
ssh -T -i "$work/vps.key" -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile="$work/vps.known" -o BatchMode=yes githubops@178.239.147.150   'ssh-keyscan -T 10 -p 1396 -t ed25519 178.239.147.125' > "$work/host.known" 2>/dev/null
test "$(ssh-keygen -lf "$work/host.known" -E sha256 | awk '{print $2}' | sort -u)" = "SHA256:7gQbDdrCVLFQRVdY6DAw8lF70jvlPfbJQslYn787E04"

cat > "$work/config" <<EOF
Host saeit-vps
  HostName 178.239.147.150
  User githubops
  IdentityFile $work/vps.key
  UserKnownHostsFile $work/vps.known
Host saeit-cpanel
  HostName 178.239.147.125
  User zomorod2
  Port 1396
  IdentityFile $work/host.key
  UserKnownHostsFile $work/host.known
  ProxyJump saeit-vps
Host *
  StrictHostKeyChecking yes
  IdentitiesOnly yes
  BatchMode yes
  ConnectTimeout 15
  ConnectionAttempts 1
  ServerAliveInterval 20
  ServerAliveCountMax 3
  ForwardAgent no
  RequestTTY no
EOF
chmod 600 "$work/config"
echo "BRIDGE_STAGE=AUTHENTICATED_OPERATION" >&2

case "$operation" in
  relay_preflight)
    timeout 45s ssh -T -F "$work/config" saeit-vps 'printf "VPS_RELAY=READY\n"'
    timeout 60s ssh -T -F "$work/config" saeit-cpanel 'printf "CPANEL_SSH=READY\n"; id -un; hostname'
    ;;
  cpanel_version)
    timeout 60s ssh -T -F "$work/config" saeit-cpanel 'uapi --output=json Version get'
    ;;
  passenger_inventory)
    timeout 60s ssh -T -F "$work/config" saeit-cpanel 'uapi --output=json PassengerApps list_applications' |
      python3 scripts/mojplaywin_cpanel_readonly_inventory.py
    ;;
  management_passenger_binding)
    timeout 60s ssh -T -F "$work/config" saeit-cpanel 'uapi --output=json PassengerApps list_applications' |
      python3 scripts/management_passenger_binding_readonly.py
    ;;
  cpanel_preflight)
    timeout 90s ssh -T -F "$work/config" saeit-cpanel 'set -e; if test -d /home/zomorod2/Saeit; then root=/home/zomorod2/Saeit; else root=/home/zomorodm/repositories/Saeit; fi; bash "$root/scripts/cpanel_preflight.sh" "$root"'
    ;;
  django_check|django_migrations)
    # The former hard-coded Python path was proved nonexistent. Until the
    # active Passenger interpreter and DB binding are attested, do not run
    # Django from a guessed venv (even for nominally read-only commands).
    echo 'CPANEL_DJANGO_PROBE_BLOCKED_UNATTESTED_ACTIVE_INTERPRETER' >&2
    exit 78
    ;;
  management_domain_docroot)
    # UAPI metadata is filtered on the runner; no raw host JSON is logged.
    timeout 60s ssh -T -F "$work/config" saeit-cpanel \
      'uapi --output=json DomainInfo single_domain_data domain=zomorodmelal.ir 2>/dev/null' |
      python3 scripts/management_domain_docroot_readonly.py
    ;;
  runtime_path_diagnostics)
    # Exact-path booleans only. No file contents, directory traversal, app
    # imports, Django commands, environment values or production mutations.
    timeout 60s ssh -T -F "$work/config" saeit-cpanel '
      set -eu
      for root in /home/zomorod2/Saeit /home/zomorodm/repositories/Saeit; do
        if test -d "$root"; then
          printf "PROJECT_ROOT=%s|present\n" "$root"
          for file in manage.py passenger_wsgi.py scripts/cpanel_preflight.sh; do
            if test -f "$root/$file"; then value=present; else value=missing; fi
            printf "PROJECT_FILE=%s/%s|%s\n" "$root" "$file" "$value"
          done
        else
          printf "PROJECT_ROOT=%s|missing\n" "$root"
        fi
      done
      for interpreter in /home/zomorod2/virtualenv/Saeit/3.11/bin/python /home/zomorodm/virtualenv/repositories/Saeit/3.11/bin/python; do
        if test -x "$interpreter"; then value=executable; else value=missing_or_not_executable; fi
        printf "PYTHON_EXECUTABLE=%s|%s\n" "$interpreter" "$value"
      done
    '
    ;;
  runtime_python_candidates)
    # Look only at precise, previously documented CloudLinux/application
    # interpreter locations. Never read config, import Python or traverse home.
    timeout 60s ssh -T -F "$work/config" saeit-cpanel '
      set -eu
      for interpreter in \
        /home/zomorod2/virtualenv/Saeit/3.9/bin/python \
        /home/zomorod2/virtualenv/Saeit/3.10/bin/python \
        /home/zomorod2/virtualenv/Saeit/3.11/bin/python3 \
        /home/zomorod2/virtualenv/Saeit/3.12/bin/python \
        /home/zomorod2/virtualenv/Saeit/3.13/bin/python \
        /home/zomorod2/virtualenv/repositories/Saeit/3.10/bin/python \
        /home/zomorod2/virtualenv/repositories/Saeit/3.11/bin/python \
        /home/zomorod2/virtualenv/repositories/Saeit/3.12/bin/python \
        /home/zomorod2/virtualenv/Saeit-staging/3.10/bin/python \
        /home/zomorod2/virtualenv/Saeit-staging/3.11/bin/python \
        /home/zomorod2/virtualenv/Saeit-staging/3.12/bin/python \
        /home/zomorod2/Saeit/.venv/bin/python \
        /home/zomorod2/Saeit/venv/bin/python; do
        if test -x "$interpreter"; then value=executable; else value=missing_or_not_executable; fi
        printf "CANDIDATE_PYTHON=%s|%s\n" "$interpreter" "$value"
      done
    '
    ;;
esac
