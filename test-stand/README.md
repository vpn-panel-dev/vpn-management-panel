# Amnezia test stand

The local stand starts the full service set with one command: admin frontend, user frontend,
backend, worker, PostgreSQL, RabbitMQ, one local VPN node, and a real Remnawave backend `remna`
with its PostgreSQL, Valkey, and local nginx reverse proxy.

After startup, the seed container creates a demo node and local users, enables Remnawave sync,
creates demo users in Remnawave, and imports them through the worker.

This stand is for local development only: all published ports are bound to `127.0.0.1`, and the
demo credentials/tokens in this file must not be used on public hosts.

## Start

```bash
cd test-stand
docker compose up --build
```

The admin panel is available at `http://localhost:8088`.

Demo access:

- login: `admin`
- password: `admin`

Test data:

- node: `Local demo node` (`http://node:8000`, endpoint `127.0.0.1:51821`)
- local users: `alice`, `bob`, `charlie`
- `charlie` is blocked immediately
- Remnawave backend: `http://remna-proxy:8080` inside Docker, `http://localhost:18081` from the host
- Remnawave superadmin: `admin` / `TestStandRemnawaveAdmin123`
- Remnawave API token: created automatically by the seed and stored in Amnezia settings
- imported users: `remna-alice`, `remna-bob`, `remna-disabled`

Ports published on `127.0.0.1`:

- `8088/tcp` — admin frontend
- `18000/tcp` — node agent for local checks
- `18081/tcp` — Remnawave backend API through the local reverse proxy
- `51821/udp` — AmneziaWG inside the container on `51820/udp`

## Re-running

The seed container is idempotent: repeated `docker compose up` runs do not duplicate the existing
node or users. It waits for the node agent and retries provisioning until the demo node reaches
`provision_status=succeeded` after the local tunnel starts. Then it registers or logs in to the
Remnawave superadmin, creates an API token and three users in Remnawave, enables Remnawave settings
in Amnezia, checks `/api/remnawave/test`, triggers `/api/remnawave/sync`, and waits for the three
Remnawave users to be imported.

To start with a clean database and node configuration:

```bash
docker compose down -v
docker compose up --build
```

## Local Docker limitations

The node uses `/dev/net/tun`, `NET_ADMIN`, and sysctls just like the main `node/docker-compose.yml`.
If the Docker host does not provide a TUN device, the `node` service will not start. In that case,
you can still inspect the panel and Remnawave services separately, but the seed will not complete
the full provision/import scenario.
