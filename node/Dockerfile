# ── Stage 1: Build awg / awg-quick CLI tools ──────────────────────────────────
FROM debian:trixie-slim AS tools-builder

RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
        git \
        build-essential \
        pkg-config \
        libmnl-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /src
RUN git clone --depth 1 https://github.com/amnezia-vpn/amneziawg-tools.git

WORKDIR /src/amneziawg-tools/src
RUN make && make install DESTDIR=/dist WITH_WGQUICK=yes


# ── Stage 2: Build amnezia-wg-go (userspace tunnel) ───────────────────────────
FROM golang:trixie AS go-builder

WORKDIR /src
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates git \
    && rm -rf /var/lib/apt/lists/* \
    && git clone --depth 1 https://github.com/amnezia-vpn/amneziawg-go.git .

RUN make


# ── Stage 3: Runtime (Python + awg tools + amneziawg-go) ─────────────────────
FROM python:3.14-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        bash \
        iproute2 \
        iptables \
        procps \
    && rm -rf /var/lib/apt/lists/*

COPY --from=tools-builder /dist/ /
COPY --from=go-builder /src/amneziawg-go /usr/local/bin/amneziawg-go

COPY agent/pyproject.toml /tmp/pyproject.toml
RUN pip install --no-cache-dir uv && uv pip install --system -r /tmp/pyproject.toml && rm /tmp/pyproject.toml

COPY agent/agent.py /app/agent.py
COPY tunnel.sh /usr/local/bin/tunnel.sh
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

RUN chmod +x /usr/local/bin/tunnel.sh

VOLUME ["/etc/amnezia/amneziawg"]

EXPOSE 51820/udp 8000

CMD ["supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
