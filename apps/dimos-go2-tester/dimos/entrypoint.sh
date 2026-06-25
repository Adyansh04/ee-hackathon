#!/usr/bin/env bash
set -Eeuo pipefail

log() {
  printf '[dimos-go2] %s\n' "$*"
}

require_env() {
  local name="$1"
  if [[ -z "${!name:-}" ]]; then
    log "ERROR: $name is required for DIMOS_MODE=${DIMOS_MODE:-unset}"
    exit 2
  fi
}

mkdir -p "${DATA_DIR:-/data/dimos}"
cd "${DATA_DIR:-/data/dimos}"

load_env_file() {
  local env_file="$1"
  if [[ ! -f "${env_file}" ]]; then
    return
  fi

  log "Sourcing environment from ${env_file}"
  while IFS= read -r line || [[ -n "${line}" ]]; do
    line="${line#"${line%%[![:space:]]*}"}"
    line="${line%"${line##*[![:space:]]}"}"
    if [[ -z "${line}" || "${line}" == \#* || "${line}" != *=* ]]; then
      continue
    fi

    local key="${line%%=*}"
    local val="${line#*=}"
    key="${key%"${key##*[![:space:]]}"}"
    val="${val#"${val%%[![:space:]]*}"}"
    val="${val%"${val##*[![:space:]]}"}"
    val="${val#\"}"
    val="${val%\"}"
    val="${val#\'}"
    val="${val%\'}"

    if [[ "${key}" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]]; then
      export "${key}=${val}"
    fi
  done < "${env_file}"
}

load_env_file "${DATA_DIR:-/data/dimos}/.env"
load_env_file "${WENDY_RUNTIME_ENV_FILE:-/app/runtime.env}"

if [[ $# -gt 0 ]]; then
  case "$1" in
    bash|sh|python|dimos|/bin/*|/usr/bin/*)
      exec "$@"
      ;;
    *)
      MODE="$1"
      shift
      ;;
  esac
else
  MODE="${DIMOS_MODE:-basic}"
fi

BLUEPRINT="${DIMOS_BLUEPRINT:-}"

case "${MODE}" in
  provision-wifi)
    if [[ $# -gt 0 ]]; then
      WIFI_SSID="$1"
      shift
    fi
    if [[ $# -gt 0 ]]; then
      WIFI_PASSWORD="$1"
      shift
    fi
    ;;
  discover|shell)
    ;;
  *)
    if [[ $# -gt 0 && -z "${ROBOT_IP:-}" ]]; then
      ROBOT_IP="$1"
      export ROBOT_IP
      shift
    fi
    if [[ "${MODE}" == "custom" && $# -gt 0 && -z "${DIMOS_BLUEPRINT:-}" ]]; then
      DIMOS_BLUEPRINT="$1"
      BLUEPRINT="$1"
      shift
    fi
    ;;
esac

if [[ $# -gt 0 ]]; then
  DIMOS_EXTRA_ARGS="$*"
fi

needs_robot_ip() {
  case "$1" in
    discover|shell|provision-wifi)
      return 1
      ;;
    *)
      return 0
      ;;
  esac
}

probe_robot_ip() {
  if [[ -n "${ROBOT_IP:-}" ]]; then
    return
  fi

  for candidate in ${ROBOT_IP_CANDIDATES:-192.168.123.161 192.168.12.1}; do
    if ping -c 1 -W 1 "${candidate}" >/dev/null 2>&1; then
      ROBOT_IP="${candidate}"
      export ROBOT_IP
      log "auto-detected robot_ip=${ROBOT_IP}"
      return
    fi
  done
}

if needs_robot_ip "${MODE}"; then
  probe_robot_ip
  if [[ "${MODE}" == "basic" && -z "${ROBOT_IP:-}" ]]; then
    MODE="discover"
  fi
fi

log "mode=${MODE}"
log "data_dir=${DATA_DIR:-/data/dimos}"

AES_KEY_FILE="${UNITREE_AES_KEY_FILE:-/data/dimos/unitree_aes_key}"
if [[ -n "${UNITREE_AES_128_KEY:-}${GO2_AES_128_KEY:-}" ]]; then
  log "unitree AES key: provided by environment"
elif [[ -s "${AES_KEY_FILE}" ]]; then
  export UNITREE_AES_KEY_FILE="${AES_KEY_FILE}"
  log "unitree AES key: using ${AES_KEY_FILE}"
else
  log "unitree AES key: not provided; newer Go2 firmware may reject WebRTC"
fi

if [[ -n "${ROBOT_IP:-}" ]]; then
  export ROBOT_IP
  log "robot_ip=${ROBOT_IP}"
  if ping -c 1 -W 2 "${ROBOT_IP}" >/dev/null 2>&1; then
    log "robot ping: ok"
  else
    log "robot ping: failed or blocked; continuing because WebRTC may still work"
  fi
else
  log "ROBOT_IP is empty"
fi

case "${MODE}" in
  discover)
    exec dimos go2tool discover
    ;;
  provision-wifi)
    require_env WIFI_SSID
    require_env WIFI_PASSWORD
    exec dimos go2tool connect-wifi --ssid "${WIFI_SSID}" --password "${WIFI_PASSWORD}"
    ;;
  basic)
    require_env ROBOT_IP
    BLUEPRINT="unitree-go2-basic"
    ;;
  nav|navigation)
    require_env ROBOT_IP
    BLUEPRINT="unitree-go2"
    ;;
  agentic)
    require_env ROBOT_IP
    if [[ -z "${OPENAI_API_KEY:-}" ]]; then
      log "WARNING: OPENAI_API_KEY is empty; agentic mode may fail"
    fi
    BLUEPRINT="unitree-go2-agentic"
    ;;
  agentic-ollama)
    require_env ROBOT_IP
    BLUEPRINT="unitree-go2-agentic-ollama"
    ;;
  spatial)
    require_env ROBOT_IP
    BLUEPRINT="unitree-go2-spatial"
    ;;
  detection)
    require_env ROBOT_IP
    log "detection mode may require editing the Dockerfile install line to dimos[base,unitree,perception] and rebuilding"
    BLUEPRINT="unitree-go2-detection"
    ;;
  shell)
    exec bash
    ;;
  custom)
    require_env ROBOT_IP
    require_env DIMOS_BLUEPRINT
    BLUEPRINT="${DIMOS_BLUEPRINT}"
    ;;
  unitree-*)
    require_env ROBOT_IP
    BLUEPRINT="${MODE}"
    ;;
  *)
    log "ERROR: unknown DIMOS_MODE=${MODE}"
    log "Valid modes: discover, provision-wifi, basic, nav, agentic, agentic-ollama, spatial, detection, shell, custom, or a unitree-* blueprint"
    exit 2
    ;;
esac

log "starting: dimos run ${BLUEPRINT} ${DIMOS_EXTRA_ARGS:-}"

EXTRA_ARGS=()
if [[ -n "${DIMOS_EXTRA_ARGS:-}" ]]; then
  read -r -a EXTRA_ARGS <<< "${DIMOS_EXTRA_ARGS}"
fi

DIMOS_VIEWER="${DIMOS_VIEWER:-${VIEWER:-rerun-web}}"
DIMOS_LISTEN_HOST="${DIMOS_LISTEN_HOST:-${LISTEN_HOST:-0.0.0.0}}"
DIMOS_MCP_PORT="${DIMOS_MCP_PORT:-${MCP_PORT:-}}"
DIMOS_N_WORKERS="${DIMOS_N_WORKERS:-${N_WORKERS:-}}"

GLOBAL_ARGS=()
if [[ -n "${ROBOT_IP:-}" ]]; then
  GLOBAL_ARGS+=(--robot-ip "${ROBOT_IP}")
fi

if [[ -n "${DIMOS_VIEWER:-}" ]]; then
  GLOBAL_ARGS+=(--viewer "${DIMOS_VIEWER}")
fi

if [[ -n "${DIMOS_LISTEN_HOST:-}" ]]; then
  GLOBAL_ARGS+=(--listen-host "${DIMOS_LISTEN_HOST}")
fi

if [[ -n "${DIMOS_MCP_PORT:-}" ]]; then
  GLOBAL_ARGS+=(--mcp-port "${DIMOS_MCP_PORT}")
fi

if [[ -n "${DIMOS_N_WORKERS:-}" ]]; then
  GLOBAL_ARGS+=(--n-workers "${DIMOS_N_WORKERS}")
fi

if [[ "${DIMOS_VIEWER}" == "rerun-web" ]]; then
  log "Forcing VIEWER=rerun-web for headless WendyOS"
fi

if [[ "${DIMOS_LISTEN_HOST}" == "0.0.0.0" ]]; then
  log "Binding DimOS web/MCP interfaces to 0.0.0.0"
fi

log "command center: http://<jetson-ip>:7779"
if [[ "${MODE}" == agentic* ]]; then
  log "agentic input: http://<jetson-ip>:5555 or MCP http://<jetson-ip>:${DIMOS_MCP_PORT:-9990}/mcp"
fi

exec dimos "${GLOBAL_ARGS[@]}" run "${BLUEPRINT}" "${EXTRA_ARGS[@]}"
