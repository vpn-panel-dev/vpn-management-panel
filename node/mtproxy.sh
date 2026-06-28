#!/bin/bash
set -euo pipefail

CONFIG_DIR="${MTPROXY_CONFIG_DIR:-/etc/amnezia/amneziawg/mtproxy}"
CONFIG_FILE="${MTPROXY_CONFIG_FILE:-${CONFIG_DIR}/config.json}"
LEGACY_CONFIG_FILE="${CONFIG_DIR}/config.env"
SECRET_FILE="${MTPROXY_PROXY_SECRET_FILE:-${CONFIG_DIR}/proxy-secret}"
MULTI_FILE="${MTPROXY_PROXY_MULTI_FILE:-${CONFIG_DIR}/proxy-multi.conf}"
PROXY_SECRET_URL="${MTPROXY_PROXY_SECRET_URL:-https://core.telegram.org/getProxySecret}"
PROXY_MULTI_URL="${MTPROXY_PROXY_MULTI_URL:-https://core.telegram.org/getProxyConfig}"
REFRESH_SECONDS="${MTPROXY_REFRESH_SECONDS:-86400}"
DRY_RUN="${MTPROXY_DRY_RUN:-0}"
SKIP_FETCH="${MTPROXY_SKIP_FETCH:-0}"

ENABLED="false"
PORT="${MTPROXY_PORT:-443}"
SECRET="${MTPROXY_SECRET:-}"
TAG="${MTPROXY_TAG:-}"
WORKERS="${MTPROXY_WORKERS:-1}"
CONTROL_PORT="${MTPROXY_CONTROL_PORT:-8888}"

log() {
    printf '[mtproxy] %s\n' "$1"
}

trim() {
    local value="$1"
    value="${value#"${value%%[![:space:]]*}"}"
    value="${value%"${value##*[![:space:]]}"}"
    printf '%s' "$value"
}

strip_quotes() {
    local value="$1"
    if [[ "${value}" == \"*\" && "${value}" == *\" ]]; then
        printf '%s' "${value:1:${#value}-2}"
        return
    fi
    if [[ "${value}" == \'*\' && "${value}" == *\' ]]; then
        printf '%s' "${value:1:${#value}-2}"
        return
    fi
    printf '%s' "${value}"
}

is_integer() {
    [[ "$1" =~ ^[0-9]+$ ]]
}

is_valid_port() {
    local value="$1"
    is_integer "${value}" && ((value >= 1 && value <= 65535))
}

is_enabled_value() {
    case "$1" in
        1|true|TRUE|yes|YES|on|ON) return 0 ;;
        *) return 1 ;;
    esac
}

read_env_config() {
    local line key value

    while IFS= read -r line || [[ -n "${line}" ]]; do
        line="$(trim "${line}")"
        [[ -z "${line}" || "${line}" == \#* || "${line}" != *=* ]] && continue

        key="$(trim "${line%%=*}")"
        value="$(trim "${line#*=}")"
        value="$(strip_quotes "${value}")"

        case "${key}" in
            ENABLED|MTPROXY_ENABLED) ENABLED="${value}" ;;
            PORT|MTPROXY_PORT) PORT="${value}" ;;
            SECRET|MTPROXY_SECRET) SECRET="${value}" ;;
            TAG|MTPROXY_TAG) TAG="${value}" ;;
            WORKERS|MTPROXY_WORKERS) WORKERS="${value}" ;;
            CONTROL_PORT|MTPROXY_CONTROL_PORT) CONTROL_PORT="${value}" ;;
        esac
    done < "${CONFIG_FILE}"
}

read_json_config() {
    local parsed

    if ! parsed="$(python3 - "${CONFIG_FILE}" <<'PY'
from __future__ import annotations

import json
import shlex
import sys
from pathlib import Path


def emit(name: str, value: object) -> None:
    print(f'{name}={shlex.quote(str(value))}')


try:
    data = json.loads(Path(sys.argv[1]).read_text())
except (OSError, json.JSONDecodeError):
    sys.exit(1)

if not isinstance(data, dict):
    sys.exit(1)

enabled = data.get('enabled', True)
emit('ENABLED', str(enabled).lower())
if enabled is False:
    sys.exit(0)

try:
    emit('PORT', data['port'])
    emit('SECRET', data['secret'])
except KeyError:
    sys.exit(1)

for source, target in (
    ('tag', 'TAG'),
    ('workers', 'WORKERS'),
    ('control_port', 'CONTROL_PORT'),
):
    if source in data:
        emit(target, data[source])
PY
)"; then
        log "Invalid MTProxy JSON config."
        exit 1
    fi

    eval "${parsed}"
}

read_config() {
    case "${CONFIG_FILE}" in
        *.json) read_json_config ;;
        *) read_env_config ;;
    esac
}

wait_for_config() {
    if [[ -f "${CONFIG_FILE}" ]]; then
        return 0
    fi

    if [[ -z "${MTPROXY_CONFIG_FILE:-}" && -f "${LEGACY_CONFIG_FILE}" ]]; then
        CONFIG_FILE="${LEGACY_CONFIG_FILE}"
        return 0
    fi

    log "Config not found at ${CONFIG_FILE}; exiting without starting MTProxy."
    return 1
}

file_mtime() {
    if stat -c %Y "$1" >/dev/null 2>&1; then
        stat -c %Y "$1"
        return
    fi
    stat -f %m "$1"
}

needs_refresh() {
    local path="$1"
    local now mtime age

    [[ ! -s "${path}" ]] && return 0
    now="$(date +%s)"
    mtime="$(file_mtime "${path}")"
    age=$((now - mtime))
    ((age >= REFRESH_SECONDS))
}

fetch_file() {
    local url="$1"
    local path="$2"
    local tmp="${path}.tmp"

    curl --fail --silent --show-error --location --output "${tmp}" "${url}"
    mv "${tmp}" "${path}"
}

refresh_telegram_config() {
    mkdir -p "${CONFIG_DIR}"

    if [[ "${SKIP_FETCH}" == "1" ]]; then
        log "Telegram config refresh skipped by environment."
        return
    fi
    if needs_refresh "${SECRET_FILE}"; then
        log "Refreshing Telegram proxy-secret."
        fetch_file "${PROXY_SECRET_URL}" "${SECRET_FILE}"
    fi
    if needs_refresh "${MULTI_FILE}"; then
        log "Refreshing Telegram proxy-multi.conf."
        fetch_file "${PROXY_MULTI_URL}" "${MULTI_FILE}"
    fi
}

validate_config() {
    if ! is_enabled_value "${ENABLED}"; then
        log "MTProxy disabled by config; exiting."
        exit 0
    fi
    if ! is_valid_port "${PORT}"; then
        log "Invalid MTProxy port in config."
        exit 1
    fi
    if ! is_valid_port "${CONTROL_PORT}"; then
        log "Invalid MTProxy control port in config."
        exit 1
    fi
    if ! is_integer "${WORKERS}" || ((WORKERS < 1)); then
        log "Invalid MTProxy worker count in config."
        exit 1
    fi
    if [[ ! "${SECRET}" =~ ^[0-9a-fA-F]{32,}$ ]]; then
        log "Invalid MTProxy secret in config."
        exit 1
    fi
}

start_mtproxy() {
    local args=(
        mtproto-proxy
        -u nobody
        -p "${CONTROL_PORT}"
        -H "${PORT}"
        -S "${SECRET}"
        --aes-pwd "${SECRET_FILE}"
        "${MULTI_FILE}"
        -M "${WORKERS}"
    )

    if [[ -n "${TAG}" ]]; then
        args+=(-P "${TAG}")
    fi

    if [[ "${DRY_RUN}" == "1" ]]; then
        log "Dry run: would start mtproto-proxy on port ${PORT} with secret redacted."
        return
    fi

    log "Starting mtproto-proxy on port ${PORT}."
    exec "${args[@]}"
}

if ! wait_for_config; then
    exit 0
fi

read_config
validate_config
refresh_telegram_config
start_mtproxy
