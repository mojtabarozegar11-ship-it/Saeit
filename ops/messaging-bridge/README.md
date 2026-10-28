# Moj messaging: persistent Telegram and two WhatsApp accounts

**Status:** implementation/source, not proof of server deployment or account authentication.
Install path: `/opt/moj-messaging`; private session state: `/var/lib/moj-messaging` (mode `0700`). Does not modify Saeit factory, MariaDB, hosting, store or websites. No messages or contacts are exported; both services are **read-only session keepers** until an independently approved private interface is added.

## What is and is not guaranteed

- **Telegram:** official Telegram MTProto protocol via Telethon 1.45.0, saves a SQLite `.session` key. New private session needs a Telegram developer `TG_API_ID` and `TG_API_HASH` from [my.telegram.org/apps](https://my.telegram.org/apps) and one local interactive login. A prior Chrome/Telegram Web session does **not** automatically transfer to Telethon.
- **WhatsApp:** Baileys linked-device (WebSocket, no Chromium) saves device authorization keys separately for `primary` and `secondary`. The library is **not an official Meta API**. Linked-device access can be revoked, expire, or be restricted by WhatsApp; account restriction is a risk. Use only personal, consented accounts and do not automate unsolicited messages. For official business integrations use Meta's WhatsApp Business Platform instead.
- Both services reconnect after transient network failures, but **no service can guarantee perpetual login** after provider revocation, account changes, or logout.
- **ChatGPT access is NOT automatically granted** by installing these services. A separate authorized, access-controlled connector would be needed. Do not publish sessions, QR codes, API hashes or chat contents through public GitHub logs, workflows, HTTP endpoints, or chat.

## Installation (Ubuntu/Debian VPS, explicit command only)

Prerequisites: `python3` with `venv`, `node` **20+**, `npm`, `systemd`, and ~200MB available. Check VPS disk/OS first. No public ports are needed.

```bash
cd /path/to/Saeit/ops/messaging-bridge
sudo bash install.sh
sudoedit /etc/moj-messaging/bridge.env   # fill TG_API_ID and TG_API_HASH locally, not in GitHub