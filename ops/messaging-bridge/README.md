# Moj messaging — private persistent Telegram and WhatsApp sessions

**Infrastructure:** isolated rootless runtime installed on the owner's VPS (Linux account `githubops`). This is a private session keeper, **not** a ChatGPT connector. It does not read, send, archive or publish conversations.

## What is installed (28 Oct 2026)

- Rootless app: `/home/githubops/private-messaging-bridge/runtime/current`
- Protected state: `/home/githubops/private-messaging-bridge/state`, permissions `0700`; session keys never enter GitHub or a public web root
- Three isolated cron keepers for Telegram, WhatsApp primary, optional WhatsApp secondary; preserve other cron jobs and leave unpaired accounts inactive
- Separate Node 22, Baileys and Telethon environments; no root/system package modifications, no public listening port
- [Original installation proof](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/40635762712) and [read-only health check](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/40635971584)
- Latest phone-code onboarding changes require their own successful deployment receipt; do not interpret source commits as live authenticated accounts

## Phone SSH key — live activation (28 October 2026)

The original Termux/ComfyUI public key `comfyui-phone-ui-20261015` has been upgraded **in-place** to allow a single, forced, interactive onboarding command. It retains `restrict` and its existing `127.0.0.1:18188` local-port forwarding allowance; no normal shell, remote commands, SCP/SFTP or other keys were enabled.

- [GitHub Actions installation and restricted-key proof](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/40640304169)
- The forced command executes `/home/githubops/private-messaging-bridge/security/phone-onboard-gate.sh`, which refuses requests without a TTY or that specify a remote command.
- On the same Android Termux environment holding the older ComfyUI phone private key, connect using the earlier recorded key path:

```bash
ssh -tt -o PasswordAuthentication=no -i ~/.ssh/comfyui-phone githubops@178.239.147.150
```

**Do not append a remote command** to this SSH invocation. After successful key authentication, the Telegram/WhatsApp wizard opens automatically and requests private one-time account pairing. No separate `sudo` or server command is needed. An older Termux setup also used `~/comfyui-phone-ui-key` as its local key path; use it only if the `~/.ssh/comfyui-phone` file is missing and that other key is confirmed to correspond to the registered public key.

A matching private key still must exist on the phone. GitHub's successful server-side change **does not verify possession of the phone's private key**, nor does it authenticate Telegram or WhatsApp.

## One-time authorization — one command in your **private** SSH terminal

After signing in to the VPS via an SSH terminal as `githubops`, run:

```bash
~/private-messaging-bridge/runtime/current/app/user-onboard.sh
```

If your laptop already has authorized SSH access to that account, run the same script in one command:

```bash
ssh -tt githubops@178.239.147.150 '~/private-messaging-bridge/runtime/current/app/user-onboard.sh'
```

The wizard skips previously saved account sessions and only requests **initial** login for missing ones:

1. **Telegram:** obtain developer API ID/hash at https://my.telegram.org/apps. The wizard accepts them **only in the private terminal**, writes a `0600` credentials file, and guides phone sign-in with the Telegram code and optional 2FA password typed privately. Your earlier Chrome/Telegram Web login is a different session and cannot be automatically reused by Telethon.
2. **WhatsApp primary:** enter your phone number in international format, digits only, then read the **eight-digit pairing code** from the private terminal. On your phone open **WhatsApp → Linked devices → Link a device → Link with phone number instead**, and enter the code. This avoids scanning a small QR.
3. **WhatsApp secondary (optional):** the wizard asks once whether to link the second account using its own phone code. You can skip it.

You may also pair WhatsApp with QR from the private terminal if phone-code pairing is rejected:

```bash
~/private-messaging-bridge/runtime/current/app/user-control.sh whatsapp-login primary
```

After pairing, existing cron keepers start authenticated sessions and restart them when the network is interrupted. **You do not need to leave your laptop online**. Provider revocation, logout or some security changes may still require another authorization.

## Check status (private SSH)

```bash
~/private-messaging-bridge/runtime/current/app/user-control.sh telegram-status
~/private-messaging-bridge/runtime/current/app/user-control.sh whatsapp-status primary
~/private-messaging-bridge/runtime/current/app/user-control.sh whatsapp-status secondary
```

A status marker is not sufficient proof of a current authenticated connection; it should be checked for recent timestamps and a running healthy process.

## Security and limitations

- **Never paste Telegram OTP/2FA, developer API hash, WhatsApp pairing codes or session files into ChatGPT/GitHub/Actions logs.** The wizard refuses noninteractive GitHub Actions runs.
- Session files are equivalent to account access: use only the private VPS and do not upload them into site backups, source control or public paths.
- WhatsApp Baileys is **unofficial** (not Meta WhatsApp Business Cloud API). Its phone-code login may fail and the service may be restricted; the QR fallback also needs only one-time pairing.
- Telegram personal MTProto login requires a new developer app and cannot access secret chats.
- These services only **keep sessions**; they do **not grant ChatGPT read access to messages**. A separate explicitly authorized, access-controlled bridge is required to read/manage chats. Nothing is accessible to ChatGPT until that integration is deployed and verified.
- No outgoing messages, financial commitments, or autonomous actions are part of this installation.
- The legacy `/opt/moj-messaging` root/systemd installer in the repository is **not the verified deployment path** on this VPS; do not run it here.
