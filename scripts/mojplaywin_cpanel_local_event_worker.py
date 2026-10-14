"""Local Unix-socket purchase event receiver for MojPlayWin cPanel staging.

Same-host, event-driven delivery: 0 external blockchain requests while idle.
A verified pending invoice wakes the reader; a close event or expiry stops it.
Only read-only blockchain indexer candidates are ever queried; no order is paid
by this process and NO AI/OpenAI API is called.

A production deployment must first configure a dedicated cPanel user process,
a durable retry outbox, owner-wallet proof and independently verified settlement.
"""
import base64
import json
import os
from pathlib import Path
import selectors
import signal
import socket
import time

from scripts.mojplaywin_purchase_events import (
    handle_verified_event, EventRejected,
)
from scripts.mojplaywin_vps_readonly_watch import scan_once, IndexerUnavailable

MAX_MESSAGE_BYTES = 3000
SOCKET_BASENAME = "native-purchase.sock"
WATCHER_INTERVAL_SECONDS = 15


class LocalEventUnavailable(ValueError):
    pass


def _get_mode(home, now_epoch):
    """Read the signed-event registry, ignoring all expired invoices."""
    source = Path(home) / "event-watch-state.json"
    if not source.exists():
        return None
    if source.is_symlink() or source.stat().st_size > 200000:
        raise LocalEventUnavailable("Unsafe event registry")
    try:
        doc = json.loads(source.read_text("utf-8"))
        invoices = doc["orders"]
        if type(invoices) is not dict:
            raise ValueError("Invalid order registry")
        active = {
            v["asset"] for v in invoices.values()
            if type(v) is dict and v.get("asset") in ("ETH", "TRX")
            and type(v.get("expires")) is int and v["expires"] > now_epoch
        }
    except (OSError, KeyError, TypeError, ValueError) as exc:
        raise LocalEventUnavailable("Invalid event registry") from exc
    if active == {"ETH", "TRX"}:
        return "BOTH"
    return next(iter(active)) if active else None


def _receive(conn, key, home, now_epoch):
    """Persist one authenticated event, then acknowledge it to Django."""
    conn.settimeout(2)
    payload = b""
    while len(payload) <= MAX_MESSAGE_BYTES and not payload.endswith(b"\n"):
        chunk = conn.recv(min(512, MAX_MESSAGE_BYTES + 1 - len(payload)))
        if not chunk:
            break
        payload += chunk
    if len(payload) > MAX_MESSAGE_BYTES or not payload.endswith(b"\n"):
        raise LocalEventUnavailable("Event envelope too large/incomplete")
    try:
        envelope = json.loads(payload.decode("ascii"))
        if type(envelope) is not dict or set(envelope) != {"payload_b64", "signature"}:
            raise ValueError("Unknown envelope fields")
        raw = base64.b64decode(envelope["payload_b64"], validate=True)
        signature = envelope["signature"]
    except (UnicodeError, ValueError, TypeError, KeyError) as exc:
        raise LocalEventUnavailable("Invalid signed event envelope") from exc
    try:
        result = handle_verified_event(raw, signature, key, home, now_epoch=now_epoch)
    except EventRejected as exc:
        raise LocalEventUnavailable("Signed purchase event rejected") from exc
    return result


def socket_request(socket_path, body, signature, *, timeout=3):
    """Django sender: local ACK means event safely persisted on same host."""
    if not isinstance(body, bytes) or len(body) > 1024:
        raise LocalEventUnavailable("Invalid event body size")
    envelope = json.dumps({
        "payload_b64": base64.b64encode(body).decode("ascii"),
        "signature": signature,
    }, separators=(",", ":")).encode("ascii") + b"\n"
    if len(envelope) > MAX_MESSAGE_BYTES:
        raise LocalEventUnavailable("Event envelope too large")
    path = Path(socket_path)
    if not path.is_absolute() or path.is_symlink():
        raise LocalEventUnavailable("Invalid local socket location")
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as conn:
        conn.settimeout(timeout)
        conn.connect(str(path))
        conn.sendall(envelope)
        answer = conn.recv(32)
        if answer != b"OK\n":
            raise LocalEventUnavailable("No authenticated delivery acknowledgement")
    return "delivered"


def run_local_worker(home, key, *, eth_scan=None, trx_scan=None,
                     stop_after_events=None, clock=time.time):
    """Block on a local socket when idle. Never poll blockchain while idle."""
    import fcntl
    from scripts.mojplaywin_direct_wallet_discovery import discover_eth, discover_trx
    if eth_scan is None:
        eth_scan = discover_eth
    if trx_scan is None:
        trx_scan = discover_trx
    home = Path(home).resolve()
    if not home.is_dir() or home.is_symlink() or home.stat().st_mode & 0o022:
        raise LocalEventUnavailable("Local watch folder must be private")
    if not isinstance(key, bytes) or len(key) < 32:
        raise LocalEventUnavailable("Event HMAC key missing")
    sock_path = home / SOCKET_BASENAME
    lock_path = home / "local-receiver.lock"
    if sock_path.is_symlink() or lock_path.is_symlink():
        raise LocalEventUnavailable("Unsafe Unix socket path")
    with lock_path.open("a+b") as lockfile:
        try:
            fcntl.flock(lockfile.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise LocalEventUnavailable("Local purchase worker already running") from exc
        if sock_path.exists():
            raise LocalEventUnavailable("A local socket already exists; verify old process")
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
            server.bind(str(sock_path))
            os.chmod(sock_path, 0o600)
            server.listen(8)
            received = 0
            try:
                while stop_after_events is None or received < stop_after_events:
                    mode = _get_mode(home, int(clock()))
                    # A pending invoice results in a 15-second wait, then
                    # an independent read-only candidate lookup.
                    timeout = WATCHER_INTERVAL_SECONDS if mode else None
                    server.settimeout(timeout)
                    try:
                        connection, _ = server.accept()
                    except socket.timeout:
                        refreshed = _get_mode(home, int(clock()))
                        if refreshed:
                            try:
                                scan_once(
                                    mode=refreshed,
                                    eth_scan=eth_scan, trx_scan=trx_scan,
                                )
                            except (IndexerUnavailable, OSError, ValueError):
                                # Retry is bounded by the invoice expiry; no
                                # candidate can change Django payment state.
                                pass
                        continue
                    with connection:
                        try:
                            result = _receive(connection, key, home, int(clock()))
                        except (OSError, LocalEventUnavailable, TimeoutError):
                            connection.sendall(b"REJECTED\n")
                        else:
                            connection.sendall(b"OK\n")
                            received += 1
                            if result["mode"]:
                                # New purchase: inspect only that chain now.
                                try:
                                    scan_once(
                                        mode=result["mode"],
                                        eth_scan=eth_scan, trx_scan=trx_scan,
                                    )
                                except (IndexerUnavailable, OSError, ValueError):
                                    pass
            finally:
                try:
                    sock_path.unlink()
                except FileNotFoundError:
                    pass


def main():
    import argparse
    parser = argparse.ArgumentParser(description="MojPlayWin cPanel local watch")
    parser.add_argument("--home", required=True)
    args = parser.parse_args()
    key = os.environ.get("MPW_NATIVE_EVENT_SECRET", "").encode("utf-8")
    os.umask(0o077)
    run_local_worker(args.home, key)


if __name__ == "__main__":
    main()
