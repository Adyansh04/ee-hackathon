#!/usr/bin/env bash
set -Eeuo pipefail

if pgrep -f "dimos run" >/dev/null 2>&1; then
  exit 0
fi

if pgrep -f "dimos go2tool" >/dev/null 2>&1; then
  exit 0
fi

exit 1
