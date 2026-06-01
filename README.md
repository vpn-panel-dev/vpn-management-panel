# Amnezia

[![Build](https://github.com/vpn-panel-dev/vpn-management-panel/actions/workflows/docker.yml/badge.svg)](https://github.com/vpn-panel-dev/vpn-management-panel/actions/workflows/docker.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Self-hosted VPN management system built on [AmneziaWG](https://github.com/amnezia-vpn/amneziawg-go) — a WireGuard fork with obfuscation.

## Architecture

```
                    ┌──────────────────────────┐
                    │     Management Server    │
                    │                          │
  Browser ───────── │  Nginx (frontend :80)    │
                    │  FastAPI (panel)         │
                    │  RabbitMQ (queue)        │
                    │  PostgreSQL (db)         │
                    └──────────┬───────────────┘
                               │ HTTP / agent API
                    ┌──────────▼───────────────┐
                    │        VPN Node          │
                    │                          │
  Clients ──UDP──── │  AmneziaWG (:51820/udp)  │
                    │  Node Agent (:8000)      │
                    └──────────────────────────┘
```

| Server | What runs on it | Exposed ports |
|---|---|---|
| VPN node | AmneziaWG + node agent | `51820/udp`, `8000` (restrict to panel IP) |
| Management panel | Panel backend + frontend + PostgreSQL | `80` |

The node agent (`8000`) must **not** be exposed to the public internet — restrict it to the management server IP via firewall.

## Docker images

Pre-built images are published to GitHub Container Registry on every push to `main`:

| Image | Description |
|---|---|
| `ghcr.io/vpn-panel-dev/amnezia-node` | AmneziaWG userspace tunnel + FastAPI agent |
| `ghcr.io/vpn-panel-dev/amnezia-panel` | FastAPI management backend |
| `ghcr.io/vpn-panel-dev/amnezia-panel-worker` | Background worker for panel jobs |
| `ghcr.io/vpn-panel-dev/amnezia-panel-frontend` | Vue 3 admin SPA served by Nginx |
| `ghcr.io/vpn-panel-dev/amnezia-user-frontend` | Vue 3 user self-service page (served at `/u/<token>`) |

---

## Deploy: VPN Node

Run on each **VPN node server**. Repeat for every node.

### Requirements

- Linux x86_64 or arm64
- Docker + Docker Compose
- Kernel with `tun` support (virtually all VPS providers)
- UDP port `51820` open in firewall

### 1. Create working directory

```bash
mkdir -p /opt/amnezia-node/config && cd /opt/amnezia-node
```

### 2. Create `docker-compose.yml`

```bash
cat > docker-compose.yml << 'EOF'
services:
  node:
    image: ghcr.io/vpn-panel-dev/amnezia-node:latest
    restart: unless-stopped
    cap_add:
      - NET_ADMIN
    devices:
      - /dev/net/tun:/dev/net/tun
    sysctls:
      - net.ipv4.ip_forward=1
      - net.ipv6.conf.all.forwarding=1
    volumes:
      - ./config:/etc/amnezia/amneziawg
    ports:
      - "51820:51820/udp"
      - "8000:8000"
    environment:
      - WG_INTERFACE=awg0
      - AGENT_TOKEN=${AGENT_TOKEN}
      - SERVER_ENDPOINT=${SERVER_ENDPOINT}
      - WG_CONFIG=/etc/amnezia/amneziawg/awg0.conf
EOF
```

### 3. Generate `.env`

This command writes a fresh random token and auto-detects the public IP:

```bash
cat > .env << EOF
AGENT_TOKEN=$(openssl rand -hex 32)
SERVER_ENDPOINT=$(curl -4 -s ifconfig.me):51820
EOF
```

### 4. Start

```bash
docker compose pull && docker compose up -d && docker compose logs --tail=30
```

The node will start and wait for the panel to send its configuration.

### 5. Restrict port 8000 to the management server

Replace `x.x.x.x` with the panel server IP:

```bash
PANEL_IP=x.x.x.x
ufw allow from $PANEL_IP to any port 8000
ufw deny 8000
ufw allow 51820/udp
ufw --force enable
```

---

## Deploy: Management Panel

Run on the **management server**.

### Requirements

- Linux x86_64 or arm64
- Docker + Docker Compose
- TCP port `80` open in firewall

### 1. Create working directory

```bash
mkdir -p /opt/amnezia-panel && cd /opt/amnezia-panel
```

### 2. Create `docker-compose.yml`

```bash
cat > docker-compose.yml << 'EOF'
services:
  frontend:
    image: ghcr.io/vpn-panel-dev/amnezia-panel-frontend:latest
    restart: unless-stopped
    ports:
      - "80:80"
    depends_on:
      - panel
      - user-frontend

  user-frontend:
    image: ghcr.io/vpn-panel-dev/amnezia-user-frontend:latest
    restart: unless-stopped
    depends_on:
      - panel

  rabbitmq:
    image: rabbitmq:4-alpine
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "rabbitmq-diagnostics", "-q", "ping"]
      interval: 5s
      timeout: 3s
      retries: 10

  panel:
    image: ghcr.io/vpn-panel-dev/amnezia-panel:latest
    restart: unless-stopped
    environment:
      - DATABASE_URL=postgresql+asyncpg://amnezia:${DB_PASSWORD}@db:5432/amnezia
      - SYNC_INTERVAL_SEC=300
      - ADMIN_PASSWORD=${ADMIN_PASSWORD}
      - SECRET_KEY=${SECRET_KEY}
    depends_on:
      db:
        condition: service_healthy
      rabbitmq:
        condition: service_healthy

  panel-worker:
    image: ghcr.io/vpn-panel-dev/amnezia-panel-worker:latest
    restart: unless-stopped
    environment:
      - RABBITMQ_URL=amqp://guest:guest@rabbitmq:5672/
      - BACKEND_INTERNAL_URL=http://panel:8080
      - WORKER_TOKEN=changeme
      - SYNC_INTERVAL_SEC=300
      - WORKER_CONCURRENCY=4
    depends_on:
      panel:
        condition: service_healthy
      rabbitmq:
        condition: service_healthy

  db:
    image: postgres:16-alpine
    restart: unless-stopped
    volumes:
      - postgres_data:/var/lib/postgresql/data
    environment:
      - POSTGRES_USER=amnezia
      - POSTGRES_PASSWORD=${DB_PASSWORD}
      - POSTGRES_DB=amnezia
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U amnezia"]
      interval: 5s
      timeout: 3s
      retries: 10

volumes:
  postgres_data:
EOF
```

### 3. Generate `.env`

```bash
cat > .env << EOF
DB_PASSWORD=$(openssl rand -hex 32)
ADMIN_PASSWORD=$(openssl rand -hex 16)
SECRET_KEY=$(openssl rand -hex 32)
REMNAWAVE_SECRET_KEY=$(openssl rand -hex 32)
EOF
```

### 4. Start

```bash
docker compose pull && docker compose up -d && docker compose logs --tail=30
```

The panel is now accessible at `http://<panel-server-ip>`.

### 5. View credentials

```bash
cat /opt/amnezia-panel/.env
```

Login: `admin` / value of `ADMIN_PASSWORD`.

---

## Connect nodes to the panel

1. Open the panel in your browser.
2. Go to **Nodes → Add node**.
3. On each node server, read its config:
   ```bash
   cat /opt/amnezia-node/.env
   ```
4. Fill in:
   - **Name** — friendly label for this node
   - **Agent URL** — `http://<node-ip>:8000`
   - **Agent token** — `AGENT_TOKEN` from the node's `.env`
   - **Endpoint** — `SERVER_ENDPOINT` from the node's `.env`
   - **Listen port** — `51820`
5. Save. The panel generates a key pair for the node and pushes the full interface config to the agent. The WireGuard interface comes up automatically.

---

## Remnawave integration

Amnezia can sync users from [Remnawave](https://remnawave.com) via API polling or webhooks.

### Setup

1. Go to **Settings → Remnawave** in the admin panel.
2. Enter your Remnawave base URL, API token, and webhook secret.
3. Set `REMNAWAVE_SECRET_KEY` in the panel environment (at least 32 characters). This key encrypts the Remnawave API token and webhook secret stored in the database.
4. Enable polling or configure Remnawave to send webhooks to `https://<panel>/api/remnawave/webhook`.

### Important notes

- Remnawave is the source of truth. Changes flow one-way from Remnawave to Amnezia.
- Remnawave-managed users are not automatically linked to existing local users.
- Imported Remnawave usage is the traffic value read from Remnawave during sync. Local AmneziaWG usage is measured from node peer counters (`rx + tx`) and stored reset-safely by Amnezia.
- For local Amnezia display and enforcement, Remnawave-managed users use combined usage: imported Remnawave traffic used plus local AmneziaWG lifetime usage.
- Local and combined AmneziaWG usage are not pushed back to Remnawave traffic counters.
- If combined usage reaches the Remnawave-imported traffic limit, Amnezia blocks the user's local peers, queues node sync, and asks Remnawave to disable the user through its lifecycle API when the integration is enabled. This does not mutate Remnawave traffic counters.
- Remnawave polling can be enabled in settings. The backend stores `polling_interval_seconds` with a default of 300 seconds; the worker checks whether polling is due once per minute.
- Without the same `REMNAWAVE_SECRET_KEY`, stored Remnawave secrets and subscription URLs cannot be decrypted after a backup restore.

## Operational semantics

- Node `online`/`offline` status currently reflects the last successful or failed sync/provision result handled by the backend. It is not an independent heartbeat and does not prove that the node is reachable right now.
- The worker automatically republishes stale `queued` operations. Operations already marked `running` are not recovered automatically today; inspect and resolve them manually until a running-operation timeout policy is implemented.

---

## Security

See [SECURITY.md](SECURITY.md) for supported versions and how to report vulnerabilities responsibly.

---

## Updating

Pull the latest images and recreate containers:

```bash
cd /opt/amnezia-node  && docker compose pull && docker compose up -d
cd /opt/amnezia-panel && docker compose pull && docker compose up -d
```

---

## Development

```
panel/
├── backend/          # FastAPI (Python)
├── admin-frontend/   # Vue 3 admin SPA
├── user-frontend/    # Vue 3 user self-service
└── docker-compose.yml
node/
├── agent/            # FastAPI node agent (Python)
└── docker-compose.yml (AmneziaWG + agent)
```

Clone the repo and use the `build:`-based compose files in each subdirectory:

```bash
# Node
cd node && docker compose up --build

# Panel
cd panel && docker compose up --build
```

---

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, code style, and how to submit changes.

## License

This project is licensed under the [MIT License](LICENSE).
