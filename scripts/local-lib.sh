#!/bin/sh
set -eu

if [ -z "${project_dir:-}" ]; then
    script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
    project_dir=$(dirname -- "$script_dir")
fi

detect_lan_ip() {
    if [ -n "${SHLB_LAN_IP:-}" ]; then
        printf '%s\n' "$SHLB_LAN_IP"
        return
    fi
    if command -v route >/dev/null 2>&1 && command -v ipconfig >/dev/null 2>&1; then
        interface=$(route -n get default 2>/dev/null | awk '/interface:/{print $2; exit}')
        if [ -n "$interface" ]; then
            ipconfig getifaddr "$interface" 2>/dev/null && return
        fi
    fi
    if command -v ip >/dev/null 2>&1; then
        ip route get 1.1.1.1 2>/dev/null | awk '{for(i=1;i<=NF;i++) if($i=="src"){print $(i+1); exit}}'
        return
    fi
    printf '127.0.0.1\n'
}

validate_ipv4() {
    printf '%s\n' "$1" | awk -F. 'NF==4 {for(i=1;i<=4;i++) if($i !~ /^[0-9]+$/ || $i<0 || $i>255) exit 1; exit 0} {exit 1}'
}

prepare_local_environment() {
    lan_ip=$(detect_lan_ip)
    if ! validate_ipv4 "$lan_ip"; then
        printf 'Unable to determine a valid LAN IPv4 address. Set SHLB_LAN_IP explicitly.\n' >&2
        exit 1
    fi
    umask 077
    {
        printf 'SHLB_LAN_IP=%s\n' "$lan_ip"
        printf 'SHLB_PUBLIC_URL=https://%s:8443\n' "$lan_ip"
        printf 'SHLB_ALLOWED_ORIGINS=https://localhost:8443,https://127.0.0.1:8443,https://%s:8443\n' "$lan_ip"
    } > "$project_dir/.env"
    printf '%s\n' "$lan_ip"
}

generate_certificate() {
    lan_ip="$1"
    cert_dir="$project_dir/.local-certs"
    temporary_dir=$(mktemp -d "${TMPDIR:-/tmp}/shlb-cert.XXXXXX")
    trap 'rm -rf "$temporary_dir"' EXIT HUP INT TERM
    umask 077
    mkdir -p "$cert_dir"
    openssl req -x509 -newkey rsa:2048 -sha256 -nodes -days 30 \
        -subj "/CN=Self Healing Load Balancer Local Lab/O=EBMSH" \
        -addext "subjectAltName=DNS:localhost,DNS:edge-nginx,IP:127.0.0.1,IP:$lan_ip" \
        -addext "keyUsage=critical,digitalSignature,keyEncipherment" \
        -addext "extendedKeyUsage=serverAuth" \
        -keyout "$temporary_dir/lab.key" \
        -out "$temporary_dir/lab.crt" >/dev/null 2>&1
    chmod 0600 "$temporary_dir/lab.key"
    chmod 0644 "$temporary_dir/lab.crt"
    mv "$temporary_dir/lab.key" "$cert_dir/lab.key"
    mv "$temporary_dir/lab.crt" "$cert_dir/lab.crt"
    trap - EXIT HUP INT TERM
    rmdir "$temporary_dir"
}

wait_for_stack() {
    deadline=$((SECONDS + 180))
    while [ "$SECONDS" -lt "$deadline" ]; do
        if docker compose ps --format json 2>/dev/null | awk 'BEGIN{ok=1;seen=0} /"Service"/{seen++} /"Health":"(starting|unhealthy)"/{ok=0} /"State":"(created|exited|restarting)"/{ok=0} END{exit !(seen>=11 && ok)}'; then
            return
        fi
        sleep 2
    done
    docker compose ps >&2
    printf 'The local stack did not become semantically healthy within 180 seconds.\n' >&2
    exit 1
}
