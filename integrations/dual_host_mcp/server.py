"""Read-only dual-host MCP bridge. No shell execution or credential storage."""
import os
import subprocess
from pathlib import Path

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Zomorod Melal Host Diagnostics", json_response=True)
HOSTS = {"cpanel": "ZM_CPANEL", "factory": "ZM_FACTORY"}
ALLOWED = {
    "uptime": "uptime",
    "disk": "df -h",
    "memory": "free -m",
    "identity": "whoami",
}
KEY_DIR = Path.home() / ".ssh"


def _host_config(target: str) -> tuple[str, str, str]:
    if target not in HOSTS:
        raise ValueError("Unknown target")
    prefix = HOSTS[target]
    host = os.environ.get(prefix + "_HOST", "")
    user = os.environ.get(prefix + "_USER", "")
    key = os.environ.get(prefix + "_KEY", "")
    if not host or not user or not key:
        raise ValueError("Target not configured")
    if not all(c.isalnum() or c in ".-_" for c in host + user):
        raise ValueError("Invalid SSH host or user")
    path = Path(key).expanduser().resolve()
    if not path.is_file() or path.is_symlink():
        raise ValueError("SSH key missing or symlinked")
    if not path.is_relative_to(KEY_DIR.resolve()):
        raise ValueError("SSH key must be under ~/.ssh")
    return host, user, str(path)


@mcp.tool()
def host_diagnostic(target: str, check: str) -> dict:
    """Run a fixed, read-only diagnostic on cpanel or factory via SSH."""
    if check not in ALLOWED:
        return {"error": "Check not permitted"}
    try:
        host, user, key = _host_config(target)
        result = subprocess.run(
            ["ssh", "-i", key, "-o", "BatchMode=yes",
             "-o", "StrictHostKeyChecking=yes",
             "-o", "ConnectTimeout=8", "-o", "ConnectionAttempts=1",
             f"{user}@{host}", ALLOWED[check]],
            capture_output=True, text=True, timeout=20, check=False,
        )
        return {"target": target, "check": check,
                "exit_code": result.returncode,
                "output": result.stdout[:6000],
                "error": result.stderr[:1000]}
    except (ValueError, OSError, subprocess.TimeoutExpired) as exc:
        return {"target": target, "check": check, "error": type(exc).__name__}


if __name__ == "__main__":
    # Local-only by default; do not expose publicly without authenticated HTTPS proxy.
    mcp.run(transport="streamable-http")
