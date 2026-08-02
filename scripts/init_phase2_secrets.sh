#!/bin/sh
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
project_dir=$(dirname -- "$script_dir")
secret_dir="$project_dir/.secrets"

umask 077
mkdir -p "$secret_dir"
chmod 0700 "$secret_dir"

write_random_secret() {
    target="$1"
    bytes="$2"
    if [ ! -f "$target" ]; then
        temporary="${target}.tmp"
        openssl rand -base64 "$bytes" | tr -d '\n' > "$temporary"
        printf '\n' >> "$temporary"
        chmod 0600 "$temporary"
        mv "$temporary" "$target"
    fi
}

write_urlsafe_key() {
    target="$1"
    if [ ! -f "$target" ]; then
        temporary="${target}.tmp"
        openssl rand -base64 32 | tr '/+' '_-' | tr -d '\n' > "$temporary"
        printf '\n' >> "$temporary"
        chmod 0600 "$temporary"
        mv "$temporary" "$target"
    fi
}

write_random_secret "$secret_dir/postgres_password" 36
write_random_secret "$secret_dir/redis_password" 36
write_random_secret "$secret_dir/bootstrap_password" 30
write_random_secret "$secret_dir/fault_control_token" 36
write_urlsafe_key "$secret_dir/field_encryption_key"

printf 'Phase 2 secret files are present in %s (values not printed).\n' "$secret_dir"
