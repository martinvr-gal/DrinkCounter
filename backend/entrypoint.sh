#!/bin/sh
set -eu

# Bind mounts can be created by Docker as root. The SQLite counter must remain
# writable after the application drops root privileges.
mkdir -p /app/counter-data /app/clips /app/uploads
chmod -R a+rwX /app/counter-data

exec runuser -u appuser -- "$@"
