#!/bin/sh
set -eu

web_root=/var/www/devlab
umask 022
stage=$(mktemp -d "$web_root/.deploy.XXXXXXXX")
trap 'rm -rf -- "$stage"' EXIT

tar --no-same-owner -xzf - -C "$stage"
test -s "$stage/index.html"

# Publish the Vite assets before switching the page that references them.
find "$stage" -mindepth 1 -type d -exec chmod 755 {} +
find "$stage" -type f -exec chmod 644 {} +
rsync -r --checksum --exclude='/index.html' -- "$stage/" "$web_root/"
clear_access_sessions
mv -Tf -- "$stage/index.html" "$web_root/index.html"
echo "Frontend published to $web_root."
