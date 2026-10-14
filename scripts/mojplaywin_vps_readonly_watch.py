"""15-second capable read-only VPS wallet watcher for MojPlayWin.

NO database access. NO wallet keys. NO transaction broadcast. NO payment state
changes. Does not depend on GitHub Actions for ongoing execution.

Polls public ETH/TRON incoming-payment indexers every 15 seconds ONLY while
a fresh, local, server-controlled pending-orders marker exists. The default
idle mode performs ZERO indexer or blockchain API requests. The local
process only checks a short-lived pending-invoice signal and sleeps.

The marker is NOT exposed on a website and must be refreshed ONLY by a
separately authenticated backend order service after production integration.
"""
import argparse
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import signal
import sys
import time

from scripts.mojplaywin_direct_wallet_discovery import (
    discover_eth, discover_trx, IndexerUnavailable,
)

ACTIVE_SECONDS = 15
IDLE_SECONDS = 60
MAX_MARKER_AGE_SECONDS = 120
RETRY_LIMIT_SECONDS = 300
VALID_MODES = frozenset({"ETH", "TRX", "BOTH"})
STOP = False


def request_stop(signum, frame):
    global STOP
    STOP = True


def get_pending_mode(marker, *, now=None):
    """Fail closed: never follow symlinks or accept stale/ambiguous modes."""
    if now is None:
        now = time.time()
    try:
        st = marker.lstat()
        if not marker.is_file() or marker.is_symlink():
            return None
        if now < st.st_mtime or now - st.st_mtime > MAX_MARKER_AGE_SECONDS:
            return None
        if st.st_size > 16 or st.st_size < 3:
            return None
        mode = marker.read_text(encoding="ascii").strip()
        return mode if mode in VALID_MODES else None
    except (OSError, UnicodeError, ValueError):
        return None


def scan_once(*, eth_scan=discover_eth, trx_scan=discover_trx, mode="BOTH"):
    """Indexer candidates only. Caller must NEVER use count as settled funds."""
    if mode not in VALID_MODES:
        raise ValueError("Invalid scanning mode")
    summary = {}
    if mode in ("ETH", "BOTH"):
        summary["ETH"] = len(eth_scan())
    if mode in ("TRX", "BOTH"):
        summary["TRX"] = len(trx_scan())
    return summary


def prepare_logger(log_path):
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log = logging.getLogger("mpw_native_wallet_watcher")
    log.setLevel(logging.INFO)
    if not log.handlers:
        handler = RotatingFileHandler(log_path, maxBytes=2_000_000, backupCount=2)
        handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)s %(message)s"))
        log.addHandler(handler)
    return log


def run_forever(home, *, time_fn=time.time, sleep=time.sleep,
                eth_scan=discover_eth, trx_scan=discover_trx,
                max_cycles=None):
    """Runs from a dedicated unprivileged VPS user directory."""
    import fcntl
    home = Path(home).resolve()
    home.mkdir(parents=True, exist_ok=True)
    lock = home / "watcher.lock"
    marker = home / "pending-orders.mode"
    logger = prepare_logger(home / "watcher.log")

    with lock.open("a+") as lockfile:
        try:
            fcntl.flock(lockfile.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            logger.info("already_running")
            return 0
        logger.info("started read_only=true no_settlement=true")
        cycle = 0
        failures = 0
        next_scan = 0.0
        last_idle_heartbeat = 0.0
        last_mode = None
        while not STOP and (max_cycles is None or cycle < max_cycles):
            cycle += 1
            now = time_fn()
            mode = get_pending_mode(marker, now=now)
            # A newly arriving order must not inherit the longer idle delay.
            if mode is not None and mode != last_mode:
                next_scan = now
            last_mode = mode
            if mode:
                interval = ACTIVE_SECONDS
                active = True
            else:
                interval = IDLE_SECONDS
                active = False
                next_scan = now
                failures = 0
            if active and now >= next_scan:
                try:
                    result = scan_once(
                        eth_scan=eth_scan, trx_scan=trx_scan,
                        mode=mode,
                    )
                    failures = 0
                    # Do not print addresses, transaction hashes or buyer data.
                    logger.info("scan_ok active=%s ETH=%s TRX=%s no_settlement=true",
                                active, result.get("ETH", "-"), result.get("TRX", "-"))
                    next_scan = now + interval
                except (IndexerUnavailable, OSError, ValueError, TimeoutError) as exc:
                    failures += 1
                    cooldown = min(RETRY_LIMIT_SECONDS, 15 * (2 ** min(failures, 4)))
                    next_scan = now + cooldown
                    logger.warning("indexer_unavailable retry_s=%s error_type=%s",
                                   cooldown, type(exc).__name__)
            elif not active and now - last_idle_heartbeat >= IDLE_SECONDS:
                logger.info("idle no_remote_calls=true no_ai_tokens=true")
                last_idle_heartbeat = now
            sleep(ACTIVE_SECONDS)
        logger.info("stopped")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Read-only native ETH TRX VPS watcher")
    parser.add_argument("--home", required=True)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--max-cycles", type=int, default=None)
    args = parser.parse_args()

    os.umask(0o077)
    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    if args.once:
        mode = get_pending_mode(Path(args.home) / "pending-orders.mode")
        if mode is None:
            print("WATCHER_IDLE_ZERO_REMOTE_REQUESTS")
            return 0
        try:
            result = scan_once(mode=mode)
        except (IndexerUnavailable, OSError, ValueError):
            print("WATCHER_READ_ONLY_PROBE_UNAVAILABLE")
            return 1
        print("WATCHER_READ_ONLY_SCAN_OK", "ETH", result.get("ETH", "-"),
              "TRX", result.get("TRX", "-"), "NO_PAYMENT_SETTLEMENT")
        return 0
    if args.max_cycles is not None and args.max_cycles < 1:
        parser.error("--max-cycles must be positive")
    return run_forever(args.home, max_cycles=args.max_cycles)


if __name__ == "__main__":
    sys.exit(main())
