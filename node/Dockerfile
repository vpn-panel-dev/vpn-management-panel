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


# ── Stage 3: Build Telegram MTProxy ───────────────────────────────────────────
FROM debian:trixie-slim AS mtproxy-builder

ARG MTPROXY_REF=cafc3380a81671579ce366d0594b9a8e450827e9

RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
        git \
        build-essential \
        libssl-dev \
        zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /src
RUN git init . \
    && git remote add origin https://github.com/TelegramMessenger/MTProxy.git \
    && git fetch --depth 1 origin "${MTPROXY_REF}" \
    && git checkout FETCH_HEAD \
    && make \
    && install -Dm755 objs/bin/mtproto-proxy /dist/usr/local/bin/mtproto-proxy


# ── Stage 4: Runtime (Python + awg tools + amneziawg-go + MTProxy) ───────────
FROM python:3.14-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        bash \
        ca-certificates \
        curl \
        iproute2 \
        iptables \
        openssl \
        procps \
    && rm -rf /var/lib/apt/lists/*

COPY --from=tools-builder /dist/ /
COPY --from=go-builder /src/amneziawg-go /usr/local/bin/amneziawg-go
COPY --from=mtproxy-builder /dist/ /

COPY agent/pyproject.toml /tmp/pyproject.toml
RUN pip install --no-cache-dir uv && uv pip install --system -r /tmp/pyproject.toml && rm /tmp/pyproject.toml

COPY agent/agent.py /app/agent.py
COPY tunnel.sh /usr/local/bin/tunnel.sh
COPY mtproxy.sh /usr/local/bin/mtproxy.sh
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

RUN chmod +x /usr/local/bin/tunnel.sh /usr/local/bin/mtproxy.sh

VOLUME ["/etc/amnezia/amneziawg", "/etc/amnezia/mtproxy"]

EXPOSE 51820/udp 8000 443/tcp

CMD ["supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
