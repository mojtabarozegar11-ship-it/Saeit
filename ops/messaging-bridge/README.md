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
```

**First and only required pairings (unless invalidated):**

```bash
sudo /opt/moj-messaging/control.sh telegram-login
sudo /opt/moj-messaging/control.sh whatsapp-login primary
sudo /opt/moj-messaging/control.sh whatsapp-login secondary
```

WhatsApp pairing QR is printed **only** in an interactive private terminal. Open WhatsApp on your phone: **Settings → Linked devices → Link a device**, and scan the QR on another screen. Do not put QR codes in public logs. Telethon login may request a code or 2FA password in the **private VPS terminal**; never send these to ChatGPT.

**Start after successful pairing:**

```bash
sudo systemctl enable --now moj-telegram.service
sudo systemctl enable --now moj-whatsapp@primary.service moj-whatsapp@secondary.service
sudo /opt/moj-messaging/control.sh telegram-status
sudo /opt/moj-messaging/control.sh whatsapp-status primary
sudo /opt/moj-messaging/control.sh whatsapp-status secondary
sudo systemctl --no-pager --full status moj-telegram moj-whatsapp@primary moj-whatsapp@secondary
```

Status is a private heartbeat file, not a proof of permission to send messages or of real-time ChatGPT access. A `CONNECTED` heartbeat must be recent (roughly within 60 seconds). For diagnostic logs use `journalctl -u moj-telegram -n 30`, etc.; scripts intentionally do not log message content or secrets.

## Security and lifecycle

- Files in `/var/lib/moj-messaging` grant **full account access**, including contacts/messages. Protect host and filesystem backups as secrets. Never synchronize this directory to GitHub, cPanel, or a public web root.
- `bridge.env` stores Telegram API credentials outside the repository with `0640 root:mojmsg` permissions. `*.session` and WhatsApp `auth` keys are never committed.
- Telegram is personal MTProto login, not a Telegram Bot API integration. It cannot access secret chats. The WhatsApp device is a linked device, not the official WhatsApp Cloud API.
- Pair WhatsApp instances **one at a time**; the second account should be linked using its own phone/app. If disconnected, re-pair only that instance.
- Revoke either connection from the respective mobile app (**Telegram > Settings > Devices**, **WhatsApp > Linked devices**), and stop service when needed: `sudo systemctl disable --now moj-telegram moj-whatsapp@primary moj-whatsapp@secondary`.
- **Do not delete** active state files to fix routine errors. Logout/revocation and operator-approved re-pairing are the only actions for invalid credentials.
- No inbound ports, mass messaging, automated replies, scraping, or syncing of third-party private messages are enabled.