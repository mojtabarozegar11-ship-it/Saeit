# PICM · MojPlayWin Private Image Studio (2026-10-15)

**Public page:** https://mojplaywin.com/picm/

Architecture: authenticated visitor → Django page and private file-backed job queue on MojPlayWin cPanel → HTTPS polling worker on existing VPS → isolated loopback-only ComfyUI `SaeitSafeCPURender` → PNG returned through authenticated Django URL. **No Termux** is involved. The VPS exposes no image-rendering HTTP port.

## Release scope
- The landing page is public, but creating images requires an existing authenticated Django user. Beta quota: 2 requests per user per 24 hours; concurrent pending cap 8 and global queue cap 80.
- Render output is **experimental 256 × 256 PNG**, not a commercial-quality 8K image. Native Tiny-SD CheckpointLoaderSimple still cannot load compressed UNet; the proven custom CPU node invokes a separate SSE2 backend.
- Requests are UTF-8 prompts with an allowlisted style and 1–3 steps only. No unrestricted ComfyUI graphs, public SSH, public arbitrary commands or external provider credentials.
- The VPS polls the site over certificate-verified HTTPS at 60-second intervals while idle; there are no per-minute ChatGPT token calls.
- Worker requests require a random per-install bearer token only in private server files. Public API requests are denied. Per-request lease prevents stale workers from replacing results.
- Images and prompts reside under `/home/zomorod2/.picm-queue` with private permissions, not under web document root. Results require the originating Django account.
- Guardrails: isolated VPS CPU, memory checks, single rendering node lock, enforced timeouts, factory PID checks and loopback-only ComfyUI.
- Worker launch is independent of GitHub Actions after initial provisioning; restart after VPS reboot must be addressed separately. A process being alive does not guarantee image quality.
- Queue is intentionally capped and should gain scheduled retention cleanup before a public production launch.
- New public-user registration, paid plans, GPU image quality, image moderation workflow and commercial-use legal approval are future release gates.

## Deployment / evidence
- Source: `core/picm_views.py`, `templates/picm/index.html`, `ops/picm-vps/worker.py`.
- Isolated installer: `scripts/deploy_mojplaywin_picm.py`, backing up prior MojPlayWin routing and touching no factory source.
- Owner-only issue trigger: `.github/workflows/mojplaywin-picm-deploy.yml`.
- Unit tests: `tests/test_picm_views.py`, workflow `.github/workflows/picm-safety-tests.yml`.
- Direct render verification: `.github/workflows/picm-live-render-proof.yml`.
- Installation success: GitHub Actions run `38721992653` (MojPlayWin HTTP 200, authenticated private HTTPS worker health, public API HTTP 403 and VPS worker start).

**Do not publish user prompts, worker tokens or PNG artifacts to the public repository.** Private authenticated downloads only.
