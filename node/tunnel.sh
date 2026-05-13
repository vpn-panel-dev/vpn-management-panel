#!/bin/bash
set -euo pipefail

INTERFACE="${WG_INTERFACE:-awg0}"
CONFIG_FILE="/etc/amnezia/amneziawg/${INTERFACE}.conf"

teardown() {
    echo "[awg] Bringing down ${INTERFACE}..."
    WG_QUICK_USERSPACE_IMPLEMENTATION=amneziawg-go \
        awg-quick down "${INTERFACE}" 2>/dev/null || true
    exit 0
}

trap teardown SIGTERM SIGINT

if [[ ! -f "${CONFIG_FILE}" ]]; then
    echo "[awg] Config not found at ${CONFIG_FILE}, waiting for provisioning from panel..."
    until [[ -f "${CONFIG_FILE}" ]]; do
        sleep 3
    done
fi

echo "[awg] Bringing up interface ${INTERFACE}..."
WG_QUICK_USERSPACE_IMPLEMENTATION=amneziawg-go awg-quick up "${INTERFACE}"

echo "[awg] Interface ${INTERFACE} is up:"
awg show "${INTERFACE}"

sleep infinity &
wait
