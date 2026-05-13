# Security Policy

## Supported versions

Only the latest release and the `main` branch are actively supported with security updates.

## Reporting a vulnerability

If you discover a security vulnerability, please **do not** open a public issue. Instead, report it privately via one of the following methods:

- Open a [GitHub Security Advisory](https://github.com/vpn-panel-dev/vpn-management-panel/security/advisories/new)
- Or email: `amnezia-panel@proton.me`

Please include as much detail as possible:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

We aim to respond within 72 hours and will keep you updated on the status of the fix.

## Security best practices for users

- Always change default passwords (`ADMIN_PASSWORD`, `AGENT_TOKEN`) before deploying.
- Keep Docker images up to date.
- Restrict the node agent port (`8000`) to the management server IP only.
- Do not commit WireGuard private keys or `.env` files to version control.
