# ComfyUI VPS Control (isolated rollout)

This branch stages an independent, opt-in ComfyUI control plane. It must NOT modify existing factory services, ports, databases or deployments.

## Deployment requirements
- Install in a separate directory and run as a dedicated unprivileged system user.
- Bind ComfyUI to 127.0.0.1 only. Never expose port 8188 publicly.
- Reach the private UI via authenticated reverse proxy or SSH tunnel, with HTTPS and access control.
- Require explicit approval before first deployment and any destructive operation.
- Use a separate systemd unit, with Restart=on-failure, CPU/RAM limits and no automatic GPU allocation to other workloads.
- Start inference only on demand; idle-stop policy configurable.
- Store secrets in VPS environment files outside Git, never in workflows/logs.
- Log job IDs, timestamps, exit codes and resource usage; do not log prompts containing private information.
- Back up configuration and test health checks before enabling.
- Existing GitHub Actions -> VPS relay is a transport, not proof that this service is running.

## Preflight checklist (read-only)
1. Verify VPS SSH connection and available disk, RAM, GPU, CUDA and Python.
2. Inventory running factory processes and occupied ports without stopping them.
3. Check whether ComfyUI already exists, to avoid duplicate installation.
4. Decide CPU-only versus GPU execution based on verified resources.
5. Prepare isolated service, health checks, rollback and private mobile access.
6. Deploy only after successful checks; preserve existing Termux setup.

## Status
Planning branch created. VPS preflight and deployment not yet executed.
