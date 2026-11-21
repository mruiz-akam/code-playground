#!/bin/sh
set -eu

app_dir=/srv/devlab
current="$app_dir/current"
venv_python="$app_dir/.venv/bin/python"
service=support-ticket-queue.service
unit_dir="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"

if [ ! -x "$venv_python" ]; then
  echo "Expected the VM's Python virtual environment at $app_dir/.venv." >&2
  exit 1
fi

if [ "$(loginctl show-user "$(id -un)" --property=Linger --value)" != yes ]; then
  echo 'Enable systemd lingering for the SSH deploy user before deploying.' >&2
  exit 1
fi

umask 077
mkdir -p "$app_dir/releases"
exec 9>"$app_dir/deploy.lock"
flock --timeout 120 9

release_dir=$(mktemp -d "$app_dir/releases/release.XXXXXXXX")
cleanup() {
  if [ "$?" -ne 0 ] && [ "$(readlink "$current" || true)" != "$release_dir" ]; then
    rm -rf -- "$release_dir"
  fi
}
trap cleanup EXIT

tar --no-same-owner -xzf - -C "$release_dir"
mkdir -p "$unit_dir"

install_dependencies() {
  "$venv_python" -m pip --disable-pip-version-check install -r "$1/requirements.txt"
}

start_release() {
  ln -sfn -- "$1" "$app_dir/current.next" &&
    mv -Tf -- "$app_dir/current.next" "$current" &&
    install -m 644 "$1/deploy/$service" "$unit_dir/$service" &&
    systemctl --user daemon-reload &&
    systemctl --user restart "$service"
}

wait_for_app() {
  attempt=0
  while [ "$attempt" -lt 15 ]; do
    if curl --noproxy '*' -fs --max-time 2 http://127.0.0.1:8000/health >/dev/null &&
      curl --noproxy '*' -fs --max-time 2 http://127.0.0.1:8000/api/tickets >/dev/null &&
      systemctl --user is-active --quiet "$service"; then
      return 0
    fi
    attempt=$((attempt + 1))
    sleep 1
  done
  return 1
}

previous_release=$(readlink "$current" || true)

if ! install_dependencies "$release_dir"; then
  echo 'Could not install dependencies for the new release.' >&2
elif start_release "$release_dir" && wait_for_app && systemctl --user enable "$service"; then
  echo 'Deployment healthy on port 8000.'
  exit 0
else
  echo 'Deployment failed its startup checks.' >&2
  systemctl --user status "$service" --no-pager --lines=15 >&2 || true
fi

if [ -n "$previous_release" ]; then
  install_dependencies "$previous_release" || echo 'Could not reinstall the previous requirements.' >&2
  if start_release "$previous_release" && wait_for_app; then
    echo 'Previous release restored.' >&2
  else
    echo 'Could not restore the previous release.' >&2
  fi
elif [ "$(readlink "$current" || true)" = "$release_dir" ]; then
  systemctl --user stop "$service"
  rm -- "$current"
fi
exit 1
