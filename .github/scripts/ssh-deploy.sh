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
remote_command=$(
  cat <<'REMOTE'
clear_access_sessions() {
  session_db=/srv/devlab/data/tickets.sqlite3
  if [ ! -e "$session_db" ]; then
    return 0
  fi

  if ! /srv/devlab/.venv/bin/python - "$session_db" <<'PYTHON'
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

database = Path(sys.argv[1]).as_uri()
with closing(sqlite3.connect(f"{database}?mode=rw", uri=True, timeout=30)) as connection, connection:
    session_table = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'access_sessions'"
    ).fetchone()
    if session_table:
        connection.execute("DELETE FROM access_sessions")
PYTHON
  then
    echo 'Could not clear lab access sessions.' >&2
    return 1
  fi
}
REMOTE
  cat -- "$remote_script"
)

ssh -F /dev/null -T -p 22 -i "$ssh_dir/key" \
  -o BatchMode=yes -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes \
  -o "UserKnownHostsFile=$ssh_dir/known_hosts" -o GlobalKnownHostsFile=/dev/null \
  -o ConnectTimeout=15 -o ServerAliveInterval=15 -o ServerAliveCountMax=3 \
  -l "$DEPLOY_USER" -- "$DEPLOY_HOST" "$remote_command"
