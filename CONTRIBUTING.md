# Contributing to Amnezia

Thanks for your interest in contributing! This document will help you get started.

## Development setup

### Prerequisites

- Python 3.14+
- [uv](https://github.com/astral-sh/uv) for Python dependency management
- Node.js 20+ (for frontends)
- Docker + Docker Compose

### Quick start

1. Clone the repository
2. Set up the **panel backend**:
   ```bash
   cd panel/backend
   uv sync --dev
   source .venv/bin/activate
   pytest
   ```
3. Set up the **node agent**:
   ```bash
   cd node/agent
   uv sync --dev
   source .venv/bin/activate
   pytest
   ```
4. Set up the **frontends**:
   ```bash
   cd panel/admin-frontend && npm install
   cd panel/user-frontend && npm install
   ```

### Running locally with Docker

```bash
# Panel (backend + frontend + db)
cd panel && docker compose up --build

# Node (agent + AmneziaWG)
cd node && docker compose up --build
```

## Code style

We use [Ruff](https://github.com/astral-sh/ruff) for linting and formatting. Pre-commit hooks are configured:

```bash
# Install pre-commit hooks
pre-commit install

# Run manually
pre-commit run --all-files
```

## Testing

- Backend and agent both use **pytest**.
- Run tests before submitting a PR:
  ```bash
  cd panel/backend && pytest
  cd node/agent && pytest
  ```

## Submitting changes

1. Fork the repository and create a feature branch.
2. Make your changes with clear, focused commits.
3. Add or update tests as needed.
4. Ensure all tests pass and linting is clean.
5. Open a Pull Request with a clear description of the change and why it's needed.

## Reporting issues

- Use [GitHub Issues](https://github.com/vpn-panel-dev/vpn-management-panel/issues) for bug reports and feature requests.
- For security issues, please see [SECURITY.md](SECURITY.md).

## Questions?

Feel free to open a [GitHub Discussion](https://github.com/vpn-panel-dev/vpn-management-panel/discussions) or ask in an issue.
