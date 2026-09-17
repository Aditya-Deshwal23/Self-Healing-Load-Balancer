#!/bin/sh
set -eu

exec python -m shlb_api.worker
