# Dual-host MCP bridge (draft; not deployed)

This isolated proof-of-concept connects to **two separate SSH destinations**: `cpanel` and `factory`. It exposes only fixed read-only diagnostics. It cannot run arbitrary commands, write files, restart services, or bypass the application's owner-approval gate.

## Requirements
- Python 3.11+, OpenSSH client and `pip install "mcp>=1.28,<2"` (v1 SDK compatibility).
- An isolated runtime outside the Django production process.
- Dedicated low-privilege SSH accounts and separate private keys under `~/.ssh`; do not commit secrets.
- Pre-verified SSH host fingerprints in `~/.ssh/known_hosts`. Never disable host-key checking.

## Environment variables
Set `ZM_CPANEL_HOST`, `ZM_CPANEL_USER`, `ZM_CPANEL_KEY`, `ZM_FACTORY_HOST`, `ZM_FACTORY_USER`, `ZM_FACTORY_KEY` in a private service environment. Key paths must be inside `~/.ssh`.

## Local test
```bash
python integrations/dual_host_mcp/server.py
```
The MCP endpoint uses streamable HTTP, local-only by default. Tools: `host_diagnostic(target, check)`; target is `cpanel` or `factory`, check is `uptime`, `disk`, `memory`, or `identity`.

## Deployment prerequisites
1. Review security and validate with isolated SSH test accounts.
2. Add authenticated TLS termination, access controls, rate limiting and audit logs before any public exposure. Never expose the default development endpoint directly.
3. Confirm that the ChatGPT account supports custom MCP registration. Creating this code **does not** register a ChatGPT plugin.
4. Obtain explicit owner approval for production deployment or future write capabilities.

No production deployment, credentials, server connection, or live diagnostics have been performed.
