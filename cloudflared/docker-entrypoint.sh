#!/bin/sh
set -eu

: "${CLOUDFLARE_TUNNEL_ID:?CLOUDFLARE_TUNNEL_ID is required}"
: "${CLOUDFLARE_API_HOSTNAME:?CLOUDFLARE_API_HOSTNAME is required}"
: "${CLOUDFLARE_DASHBOARD_HOSTNAME:?CLOUDFLARE_DASHBOARD_HOSTNAME is required}"

if [ ! -f /etc/cloudflared/credentials.json ]; then
  echo "Missing cloudflared credentials file at /etc/cloudflared/credentials.json" >&2
  exit 1
fi

envsubst < /etc/cloudflared/config.template.yml > /etc/cloudflared/config.yml

exec /usr/local/bin/cloudflared tunnel --config /etc/cloudflared/config.yml run
