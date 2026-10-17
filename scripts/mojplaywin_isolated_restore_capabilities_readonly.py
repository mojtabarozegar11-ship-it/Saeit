#!/usr/bin/env python3
"""VPS-only read-only capability check for isolated MojPlayWin restore.
No source files, keys, DB rows, hostnames or private paths read or printed.
No docker pull/build/create, SQL connection, service startup, writes or restarts.
"""
import json, os, shutil, subprocess
from pathlib import Path


def works(args, timeout=5):
    try:
        proc=subprocess.run(args,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=timeout,check=False)
        return proc.returncode==0
    except (OSError, subprocess.TimeoutExpired):
        return False

def inspect():
    cmds={name:bool(shutil.which(name)) for name in
          ("docker","podman","mariadbd","mysqld","mariadb-install-db",
           "mysql_install_db","mariadb","mysql","python3","tar","gpg","gzip")}
    free=None
    try:
        s=os.statvfs(Path.home()); free=s.f_bavail*s.f_frsize
    except OSError:
        pass
    mem=None
    try:
        with open("/proc/meminfo",encoding="ascii") as f:
            for line in f:
                if line.startswith("MemAvailable:"):
                    mem=int(line.split()[1])*1024
                    break
    except (OSError,ValueError):
        pass
    return {
        "classification":"READ_ONLY_ISOLATED_RESTORE_CAPABILITIES",
        "commands_present":cmds,
        "docker_daemon_accessible":cmds["docker"] and works(["docker","info","--format","{{.ServerVersion}}"]),
        "podman_rootless_accessible":cmds["podman"] and works(["podman","info","--format","{{.Host.Security.Rootless}}"]),
        "mariadb_selfcontained_runtime_present":bool(cmds["mariadbd"] or cmds["mysqld"]) and bool(cmds["mariadb-install-db"] or cmds["mysql_install_db"]),
        "free_bytes":free,
        "memory_available_bytes":mem,
        "isolated_restore_performed":False,
        "live_database_modified":False,
        "release_permitted":False
    }

if __name__=="__main__":
    print(json.dumps(inspect(),sort_keys=True))
