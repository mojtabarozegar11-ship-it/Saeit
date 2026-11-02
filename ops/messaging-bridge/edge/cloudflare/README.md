# Optional Cloudflare Workers Free WebSocket egress

**State (2026-10-28): source staged and unit-tested; NOT DEPLOYED.**
No WhatsApp pairing, authentication, message access, social posting, or egress success through Cloudflare has been claimed.

## Purpose and limits

This is a private, destination-restricted experiment to connect the existing rootless
WhatsApp Baileys keeper on the VPS to the WhatsApp Web chat WebSocket endpoint via
Cloudflare Workers. It is not a generic HTTP/SOCKS proxy and it does not provide
an always-on VM. Baileys remains on the original isolated VPS; app credentials
remain in its protected state directory. The Worker neither persists nor logs
account sessions, raw messages, or authentication credentials.

**Only WebSocket chat transport is covered.** WhatsApp media URLs, uploads,
downloads, other API hosts, and additional social networks are NOT proxied.
They require separate authorized connectors and network checks. Baileys is an
unofficial WhatsApp Web integration; connection success cannot be guaranteed.

## Prerequisites requiring a verified Cloudflare account

1. Sign up at https://dash.cloudflare.com/sign-up with a valid email and
   complete any account/email verification. Use the **Workers Free** plan.
   Do not enter payment details or upgrade to a paid plan for this task.
2. The selected Worker name is moj-social-wa-edge by default. Its public
   workers.dev hostname must be obtained from Cloudflare after real deployment;
   do not guess it.
3. Create a strong, random URL-safe shared token (at least 32 bytes of entropy).
   Store the same token as Cloudflare Worker secret BRIDGE_SHARED_TOKEN and
   privately on the VPS under the rootless messaging service as
   MOJMSG_WA_EDGE_TOKEN; NEVER put it in source control, chat, action logs,
   email, or a URL you share with others.
4. Store the deployed Worker origin, such as
   wss://<worker>.<account>.workers.dev, privately as MOJMSG_WA_EDGE_BASE
   (without a path). The optional Baileys code will create the strict
   /bridge/<private-token>/ws/chat URL at runtime.
5. Only after a verified Worker deployment, test /health, authenticated
   WebSocket upgrade, TLS and app connection status in isolation. Then perform
   a private one-time phone linked-device pairing if required.

Use only official Cloudflare dashboard/secret mechanisms for deployment. Do not
publish tokens as plaintext configuration, request paths in logs, or repository
secrets. The private URL path contains a bearer credential for WebSocket clients
that lack a separate per-WebSocket header; the token must be protected and can be
rotated.

## Operational safety

- Feature flag is OFF by default: no EDGE env vars means the original Baileys
  direct connection behavior remains unchanged.
- Do not modify DNS, firewall, system proxy, Tailscale, or cPanel live sites.
- No wildcard destinations, no arbitrary host forwarding, no account content logging.
- Do not enable social messaging, publishing, or external writes until each platform
  account authorizes the corresponding official API connector (where available).
- If Worker free quota, policy, region or upstream Meta access prevents this
  design, stop rather than silently falling back to insecure TLS or a paid tier.
- Successful unit tests do not demonstrate that WhatsApp accepts the Worker
  egress IP, that a stable session is established, or that free-tier availability
  is suitable for long-running use.

## Sources

- https://developers.cloudflare.com/workers/platform/pricing/
- https://developers.cloudflare.com/workers/examples/websockets/
- https://developers.cloudflare.com/workers/configuration/secrets/
- https://github.com/WhiskeySockets/Baileys/blob/master/src/Types/Socket.ts
