#!/bin/sh
set -eu

PORT="${QPS_DEBUG_CONTAINER_PORT:-4711}"
exec lldb-server gdbserver "0.0.0.0:${PORT}" /opt/qps-debug/probe
