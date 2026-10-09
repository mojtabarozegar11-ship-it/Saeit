# Staging hosting reverse SSH tunnel (prepared, NOT activated)
This is an alternative when VPS -> hosting inbound SSH is filtered.
Scope: staging infrastructure only. No Production, main branch, PR merge, or host filesystem changes are performed by the GitHub commit.

## Network path
Hosting account -> outbound TCP/22 -> VPS 178.239.147.150 (githubops)
SSH remote forward: VPS loopback 127.0.0.1:22222 -> hosting loopback 127.0.0.1:22.
The port 22222 must NEVER be opened in VPS firewall or bound to 0.0.0.0.
This is a tunnel, NOT proof of successful login to hosting. Hosting SSH may use a different port; set HOST_SSH_PORT to the verified host-side SSH port.

## Host-side one-time setup
Run `bash scripts/staging/install-host-reverse-tunnel.sh` in the hosting account.
The script generates an ED25519 key on the hosting account and prints ONLY the public key.
An authorized VPS administrator must append that public key to
`/home/githubops/.ssh/authorized_keys` with restrictions such as
`restrict,port-forwarding,permitlisten="127.0.0.1:22222"`
after checking the server supports these OpenSSH authorized_keys options.
Use a dedicated restricted account rather than githubops if practical.
Then run `~/.zomorod-staging-tunnel/run.sh` on hosting.
Configure a supervised restart only after successful testing and authorization.

## Validation and safety
From VPS: `ssh -p 22222 -o BatchMode=yes 127.0.0.1` requires a separately authorized HOSTING key and pinned HOSTING host key; do not disable host-key checking in actual use.
Only the hosting account can initiate the tunnel. A working GitHub -> VPS link does not grant hosting access.
Never put private keys in repository, logs, or messages. Do not automate financial or production operations.
This repository only prepares the installer and documentation. It cannot execute it on hosting until an authorized hosting session exists.
