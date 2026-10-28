#!/usr/bin/env python3
"""Private Telegram MTProto session keeper; no message collection or sending."""
import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path


def state_root():
    path = Path(os.environ.get('MOJMSG_STATE_DIR', '/var/lib/moj-messaging')).resolve()
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(path, 0o700)
    return path


def status_write(root, status):
    path = root / 'telegram-status.json'
    tmp = root / f'.telegram-status-{os.getpid()}.tmp'
    tmp.write_text(json.dumps({'service': 'telegram', 'status': status,
                               'timestamp': int(time.time())}) + '\n', encoding='utf-8')
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)


async def heartbeat(root, interval=30):
    while True:
        status_write(root, 'CONNECTED')
        await asyncio.sleep(interval)


async def main(mode):
    from telethon import TelegramClient
    api_id = os.environ.get('TG_API_ID')
    api_hash = os.environ.get('TG_API_HASH')
    if not api_id or not api_hash:
        print('TG_API_ID and TG_API_HASH must be configured privately.', file=sys.stderr)
        return 2
    root = state_root()
    session_base = str(root / 'telegram' / 'account')
    (root / 'telegram').mkdir(mode=0o700, exist_ok=True)
    os.chmod(root / 'telegram', 0o700)
    client = TelegramClient(session_base, int(api_id), api_hash, auto_reconnect=True,
                            connection_retries=5, request_retries=3)
    try:
        if mode == 'login':
            # start() only requests credentials when the saved session is absent/invalid.
            await client.start(phone=lambda: input('Telegram phone (+country code): '),
                               code_callback=lambda: input('Telegram sign-in code (local terminal only): '),
                               password=lambda: __import__('getpass').getpass('Telegram 2FA password: '))
            print('AUTHORIZED: Telegram session saved privately; never commit *.session.')
            status_write(root, 'AUTHORIZED')
            return 0
        if mode == 'status':
            file = root / 'telegram-status.json'
            print(file.read_text().strip() if file.exists() else 'NOT_STARTED')
            return 0
        await client.connect()
        if not await client.is_user_authorized():
            status_write(root, 'LOGIN_REQUIRED')
            print('LOGIN_REQUIRED: use local control.sh telegram-login', file=sys.stderr)
            return 3
        status_write(root, 'CONNECTED')
        beat = asyncio.create_task(heartbeat(root))
        try:
            await client.run_until_disconnected()
        finally:
            beat.cancel()
            await asyncio.gather(beat, return_exceptions=True)
        return 1
    except (KeyboardInterrupt, asyncio.CancelledError):
        return 0
    finally:
        await client.disconnect()
        if mode == 'daemon':
            status_write(root, 'DISCONNECTED')


if __name__ == '__main__':
    os.umask(0o077)
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=('login', 'daemon', 'status'))
    args = parser.parse_args()
    try:
        raise SystemExit(asyncio.run(main(args.mode)))
    except Exception as exc:
        # Never log session secrets or incoming message data.
        print(f'Telegram error: {type(exc).__name__}', file=sys.stderr)
        raise SystemExit(1)