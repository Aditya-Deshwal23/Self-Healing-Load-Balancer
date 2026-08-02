#!/bin/sh
set -eu

cert_dir=/etc/nginx/tls
cert_file="$cert_dir/lab.crt"
key_file="$cert_dir/lab.key"

mkdir -p "$cert_dir"

if [ ! -s "$cert_file" ] || [ ! -s "$key_file" ]; then
  openssl req -x509 -newkey rsa:2048 -sha256 -nodes -days 7 \
    -subj "/CN=localhost/O=Self Healing Load Balancer Phase 1" \
    -addext "subjectAltName=DNS:localhost,DNS:edge-nginx,IP:127.0.0.1" \
    -keyout "$key_file" \
    -out "$cert_file"
  chmod 0600 "$key_file"
fi

