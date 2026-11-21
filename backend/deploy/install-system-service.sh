#!/bin/sh
set -eu

if [ "$(id -u)" -ne 0 ]; then
  echo 'Run this installer with sudo on the VM.' >&2
  exit 1
fi

app_dir=/srv/devlab
service=support-ticket-queue.service
systemctl=/usr/bin/systemctl
unit_source="$(dirname "$0")/$service"
deploy_runtime_dir="/run/user/$(id -u deploy)"

deploy_systemctl() {
  sudo -u deploy env XDG_RUNTIME_DIR="$deploy_runtime_dir" "$systemctl" --user "$@"
}

# Share the lock with the release script, with the file owned by deploy.
sudo -u deploy sh -c 'umask 077; : >> "$1"' sh "$app_dir/deploy.lock"
exec 9<"$app_dir/deploy.lock"
flock --timeout 120 9

legacy_enabled=no
legacy_active=no
if [ -S "$deploy_runtime_dir/bus" ]; then
  if deploy_systemctl is-enabled --quiet "$service"; then
    legacy_enabled=yes
  fi
  if deploy_systemctl is-active --quiet "$service"; then
    legacy_active=yes
  fi
else
  deploy_home=$(getent passwd deploy | cut -d: -f6)
  if [ -L "$deploy_home/.config/systemd/user/default.target.wants/$service" ]; then
    echo 'The legacy unit is enabled. Start the deploy user manager so it can be disabled during migration.' >&2
    exit 1
  fi
fi

sudoers_file=$(mktemp)
trap 'rm -f -- "$sudoers_file"' EXIT
printf 'deploy ALL=(root) NOPASSWD: %s restart %s, %s stop %s\n' \
  "$systemctl" "$service" "$systemctl" "$service" >"$sudoers_file"
visudo -cf "$sudoers_file"
install -o root -g root -m 0440 "$sudoers_file" /etc/sudoers.d/support-ticket-queue
install -o root -g root -m 0644 "$unit_source" "/etc/systemd/system/$service"
"$systemctl" daemon-reload

restore_legacy() {
  if [ "$legacy_enabled" = yes ]; then
    deploy_systemctl enable "$service" || echo 'Could not re-enable the legacy user service.' >&2
  fi
  if [ "$legacy_active" = yes ]; then
    deploy_systemctl start "$service" || echo 'Could not restart the legacy user service.' >&2
  fi
}

if [ "$legacy_enabled" = yes ] || [ "$legacy_active" = yes ]; then
  if ! deploy_systemctl disable --now "$service"; then
    restore_legacy
    exit 1
  fi
fi

if [ ! -f "$app_dir/current/app/main.py" ]; then
  "$systemctl" enable "$service"
  echo "System service enabled. The first backend deployment will start it."
elif "$systemctl" enable --now "$service" &&
  curl --noproxy '*' -fsS --retry 10 --retry-delay 1 --retry-connrefused --max-time 2 \
    http://127.0.0.1:8000/health >/dev/null &&
  curl --noproxy '*' -fsS --max-time 2 http://127.0.0.1:8000/api/tickets >/dev/null &&
  "$systemctl" is-active --quiet "$service"; then
  echo 'System service is active and API checks passed.'
else
  "$systemctl" status "$service" --no-pager >&2 || true
  if [ "$legacy_enabled" = yes ] || [ "$legacy_active" = yes ]; then
    if "$systemctl" disable --now "$service"; then
      restore_legacy
    else
      echo 'Could not stop the system service before restoring the legacy service.' >&2
    fi
  fi
  exit 1
fi
