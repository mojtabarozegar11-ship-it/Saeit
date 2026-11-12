#!/usr/bin/env bash
# Strict public HOMEPAGE HTML guard. No writes to the website or accounting data.
# The guard refuses deployment when page response varies even before install.
set -Eeuo pipefail
umask 077

homepage_digest() {
  # Strict TLS, no insecure redirects or missing responses. Never log page HTML.
  local result
  result="$(curl --fail --silent --show-error --location \
      --proto '=https' --proto-redir '=https' \
      --connect-timeout 10 --max-time 25 --max-redirs 3 \
      --max-filesize 2000000 \
      'https://zomorodmelal.ir/' | sha256sum | awk '{print $1}')"
  [[ "$result" =~ ^[0-9a-f]{64}$ ]] || return 2
  printf '%s\n' "$result"
}

case "${1:-}" in
  capture)
    [[ "$#" -eq 1 ]] || exit 2
    first="$(homepage_digest)"
    second="$(homepage_digest)"
    [[ "$first" == "$second" ]] || {
      echo 'PUBLIC_HOMEPAGE_GUARD=UNSTABLE_BASELINE_ABORT' >&2
      exit 4
    }
    printf '%s\n' "$first"
    ;;
  verify)
    [[ "$#" -eq 2 && "$2" =~ ^[0-9a-f]{64}$ ]] || exit 2
    first="$(homepage_digest)"
    second="$(homepage_digest)"
    [[ "$first" == "$2" && "$second" == "$2" ]] || {
      echo 'PUBLIC_HOMEPAGE_GUARD=CONTENT_CHANGED_ROLLBACK' >&2
      exit 4
    }
    echo 'PUBLIC_HOMEPAGE_HTML_UNCHANGED=VERIFIED'
    ;;
  *)
    echo 'PUBLIC_HOMEPAGE_GUARD=UNKNOWN_OPERATION' >&2
    exit 2
    ;;
esac
