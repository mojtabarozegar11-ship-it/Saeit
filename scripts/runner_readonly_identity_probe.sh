#!/usr/bin/env bash
# Read-only local identity/access probe. No network, sudo, restarts, or writes.
set -u
printf 'effective_uid=%s\n' "$(id -u)"
printf 'effective_user=%s\n' "$(id -un)"
printf 'primary_gid=%s\n' "$(id -g)"
printf 'hostname=%s\n' "$(hostname)"
printf 'pwd=%s\n' "$PWD"
if [ "$#" -ne 1 ]; then
  printf 'usage: %s ABSOLUTE_FACTORY_ROOT\n' "$0" >&2
  exit 64
fi
case "$1" in /*) ;; *) echo 'factory_root_must_be_absolute' >&2; exit 64;; esac
root="$1"
if [ ! -e "$root" ]; then echo 'factory_root=missing'; exit 2; fi
if [ -L "$root" ]; then echo 'factory_root=symlink_refused'; exit 3; fi
if [ ! -d "$root" ]; then echo 'factory_root=not_directory'; exit 3; fi
if [ -r "$root" ] && [ -x "$root" ]; then echo 'factory_root=readable_traversable'; else echo 'factory_root=access_denied'; exit 4; fi
printf 'factory_root_canonical=%s\n' "$(cd -- "$root" && pwd -P)"
