#!/usr/bin/env bash
set -euo pipefail

remote_script=${1:?Pass the path to the VM deployment script}
: "${DEPLOY_HOST:?Set the DEPLOY_HOST environment secret}"
: "${DEPLOY_USER:?Set the DEPLOY_USER environment secret}"
: "${DEPLOY_SSH_KEY:?Set the DEPLOY_SSH_KEY environment secret}"
: "${DEPLOY_KNOWN_HOSTS:?Set the DEPLOY_KNOWN_HOSTS environment variable}"

umask 077
ssh_dir=$(mktemp -d "$RUNNER_TEMP/support-queue-ssh.XXXXXXXX")
trap 'rm -rf -- "$ssh_dir"' EXIT
printf '%s\n' "$DEPLOY_SSH_KEY" > "$ssh_dir/key"
printf '%s\n' "$DEPLOY_KNOWN_HOSTS" > "$ssh_dir/known_hosts"
remote_command=$(cat -- "$remote_script")

ssh -F /dev/null -T -p 22 -i "$ssh_dir/key" \
  -o BatchMode=yes -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes \
  -o "UserKnownHostsFile=$ssh_dir/known_hosts" -o GlobalKnownHostsFile=/dev/null \
  -o ConnectTimeout=15 -o ServerAliveInterval=15 -o ServerAliveCountMax=3 \
  -l "$DEPLOY_USER" -- "$DEPLOY_HOST" "$remote_command"
