"""Signed purchase-event signal core for MojPlayWin (isolated staging).

Events are emitted *after* an authenticated checkout commits a pending native
ETH/TRX invoice. VPS handler aggregates open invoices and writes one local
marker. Marker means *start a read-only check*, NEVER *mark an order paid*.

No OpenAI or other AI API is used. HTTPS ingress must be provisioned and
tested separately; never expose this receiver over plaintext public HTTP.
"""
from contextlib import contextmanager
from hashlib import sha256
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import time

VALID_ASSETS = frozenset(("ETH", "TRX"))
VALID_ACTIONS = frozenset(("invoice_open", "invoice_closed"))
MAX_EVENT_BYTES = 1024
MAX_EVENT_AGE_S = 90
MAX_ORDER_LIFETIME_S = 1200
NONCE_LIFETIME_S = 240


class EventRejected(ValueError):
    pass


def make_event(action, invoice_id, order_id, asset, expires_at_epoch, *, now_epoch=None):
    if now_epoch is None:
        now_epoch = int(time.time())
    if action not in VALID_ACTIONS or asset not in VALID_ASSETS:
        raise EventRejected("Unknown action or chain asset")
    if (type(invoice_id) is not int or invoice_id <= 0 or
        type(order_id) is not int or order_id <= 0 or
        type(now_epoch) is not int or now_epoch < 1700000000 or
        type(expires_at_epoch) is not int):
        raise EventRejected("Invalid order identifiers or timestamps")
    if action == "invoice_open" and not (
        now_epoch < expires_at_epoch <= now_epoch + MAX_ORDER_LIFETIME_S
    ):
        raise EventRejected("Pending invoice lifespan exceeds cap")
    return {
        "v": 1,
        "action": action,
        "invoice": invoice_id,
        "order": order_id,
        "asset": asset,
        "expires": expires_at_epoch,
        "sent": now_epoch,
        "nonce": secrets.token_hex(16),
    }


def signed_message(event, key):
    if not isinstance(key, bytes) or len(key) < 32:
        raise EventRejected("At least 32 bytes of private notification key required")
    body = json.dumps(event, sort_keys=True, separators=(",", ":")).encode("ascii")
    if len(body) > MAX_EVENT_BYTES:
        raise EventRejected("Oversized event")
    return body, "sha256=" + hmac.new(key, body, sha256).hexdigest()


def verify_event(body, signature, key, *, now_epoch=None):
    if now_epoch is None:
        now_epoch = int(time.time())
    if not isinstance(body, bytes) or len(body) > MAX_EVENT_BYTES:
        raise EventRejected("Invalid message size")
    if not isinstance(signature, str) or not re.fullmatch(r"sha256=[0-9a-f]{64}", signature):
        raise EventRejected("Invalid event authentication")
    _, correct_signature = signed_message({"v":1}, key)  # validate key first
    correct_signature = "sha256=" + hmac.new(key, body, sha256).hexdigest()
    if not hmac.compare_digest(signature, correct_signature):
        raise EventRejected("Event signature mismatch")
    try:
        event = json.loads(body.decode("ascii"))
    except (ValueError, UnicodeDecodeError):
        raise EventRejected("Invalid signed JSON")
    if type(event) is not dict or set(event) != {
        "v", "action", "invoice", "order", "asset", "expires", "sent", "nonce"
    }:
        raise EventRejected("Invalid event fields")
    if (event["v"] != 1 or event["action"] not in VALID_ACTIONS
        or event["asset"] not in VALID_ASSETS
        or type(event["order"]) is not int or event["order"] <= 0
        or type(event["invoice"]) is not int or event["invoice"] <= 0
        or type(event["sent"]) is not int or type(now_epoch) is not int
        or abs(now_epoch - event["sent"]) > MAX_EVENT_AGE_S
        or type(event["expires"]) is not int
        or not isinstance(event["nonce"], str)
        or not re.fullmatch(r"[0-9a-f]{32}", event["nonce"])):
        raise EventRejected("Event invalid or expired")
    if event["action"] == "invoice_open" and not (
        now_epoch < event["expires"] <= now_epoch + MAX_ORDER_LIFETIME_S
    ):
        raise EventRejected("Invoice expired or outside maximum watch window")
    return event


def _safe_directory(home):
    home = Path(home).resolve()
    if not home.is_dir() or home.is_symlink():
        raise EventRejected("Unsafe watcher directory")
    if home.stat().st_mode & 0o022:
        raise EventRejected("Watcher directory is group/world writable")
    return home


def _write_atomic(directory, name, content):
    tmp = directory / ("." + name + ".tmp." + secrets.token_hex(8))
    fd = os.open(str(tmp), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        with os.fdopen(fd, "wb") as fp:
            fp.write(content)
            fp.flush()
            os.fsync(fp.fileno())
        os.replace(str(tmp), str(directory / name))
    finally:
        try:
            tmp.unlink()
        except FileNotFoundError:
            pass


def handle_verified_event(body, signature, key, home, *, now_epoch=None):
    """Only signed events change local *watch* state, NEVER orders or balances."""
    import fcntl
    if now_epoch is None:
        now_epoch = int(time.time())
    event = verify_event(body, signature, key, now_epoch=now_epoch)
    directory = _safe_directory(home)
    state_file = directory / "event-watch-state.json"
    marker = directory / "pending-orders.mode"
    if state_file.is_symlink() or marker.is_symlink():
        raise EventRejected("Unsafe event state path")
    lock = directory / "event-watch.lock"
    if lock.is_symlink():
        raise EventRejected("Unsafe lock path")
    with open(lock, "a+b") as fp:
        fcntl.flock(fp.fileno(), fcntl.LOCK_EX)
        if state_file.exists():
            if state_file.stat().st_size > 200_000:
                raise EventRejected("Oversized watch state")
            try:
                state = json.loads(state_file.read_text("utf-8"))
                if not isinstance(state, dict):
                    raise ValueError("state not mapping")
                orders = state.get("orders", {})
                seen = state.get("seen", {})
                if not isinstance(orders, dict) or not isinstance(seen, dict):
                    raise ValueError("state fields invalid")
            except (OSError, ValueError):
                raise EventRejected("State unreadable; refuse to overwrite")
        else:
            orders, seen = {}, {}
        orders = {k:v for k,v in orders.items()
                  if (isinstance(v, dict) and type(v.get("expires")) is int
                      and v["expires"] > now_epoch
                      and v.get("asset") in VALID_ASSETS)}
        seen = {k:v for k,v in seen.items()
                if type(v) is int and v + NONCE_LIFETIME_S > now_epoch}
        if event["nonce"] in seen:
            raise EventRejected("Replay attempt")
        seen[event["nonce"]] = now_epoch
        idx = str(event["invoice"])
        if event["action"] == "invoice_open":
            orders[idx] = {
                "order": event["order"],
                "asset": event["asset"],
                "expires": event["expires"],
            }
        else:
            current = orders.get(idx)
            if current and current["order"] == event["order"] and current["asset"] == event["asset"]:
                orders.pop(idx)
        if len(orders) > 1000 or len(seen) > 10000:
            raise EventRejected("Event state capacity exceeded")
        _write_atomic(directory, state_file.name,
                      json.dumps({"orders":orders,"seen":seen},sort_keys=True).encode("ascii"))
        current_assets = {x["asset"] for x in orders.values()}
        if len(current_assets) == 2:
            mode = "BOTH"
        elif current_assets:
            mode = next(iter(current_assets))
        else:
            mode = None
        if mode:
            _write_atomic(directory, marker.name, (mode + "\n").encode("ascii"))
        else:
            marker.unlink(missing_ok=True)
        return {"state":"watching" if mode else "idle",
                "open_invoices":len(orders),"mode":mode}
