#!/bin/sh
set -eu

app_dir=/srv/devlab
current="$app_dir/current"
venv_python="$app_dir/.venv/bin/python"
service=support-ticket-queue.service
systemctl=/usr/bin/systemctl

if [ ! -x "$venv_python" ]; then
  echo "Expected the VM's Python virtual environment at $app_dir/.venv." >&2
  exit 1
fi

umask 077
mkdir -p "$app_dir/releases"
exec 9>"$app_dir/deploy.lock"
flock --timeout 120 9

if ! "$systemctl" is-enabled --quiet "$service"; then
  echo 'Install and enable the system service on the VM with backend/deploy/install-system-service.sh.' >&2
  exit 1
fi

if ! sudo -n -l "$systemctl" restart "$service" >/dev/null ||
  ! sudo -n -l "$systemctl" stop "$service" >/dev/null; then
  echo "The deploy user needs passwordless sudo for restart and stop of $service." >&2
  exit 1
fi

release_dir=$(mktemp -d "$app_dir/releases/release.XXXXXXXX")
env_file="$app_dir/.env"
previous_env="$release_dir/.previous-env"
env_replaced=no
cleanup() {
  result=$?
  rm -f -- "$release_dir/.env"
  if [ "$result" -ne 0 ] && [ ! -f "$previous_env" ] &&
    [ "$(readlink "$current" || true)" != "$release_dir" ]; then
    rm -rf -- "$release_dir"
  fi
}
trap cleanup EXIT

tar --no-same-owner -xzf - -C "$release_dir"
if [ ! -s "$release_dir/.env" ]; then
  echo 'The release is missing the access token configuration.' >&2
  exit 1
fi
chmod 600 "$release_dir/.env"

if ! "$venv_python" -m pip --version >/dev/null 2>&1; then
  set -- "$release_dir"/pip-bootstrap/pip-*.whl
  if [ "$#" -ne 1 ] || [ ! -f "$1" ]; then
    echo 'The release must include one pip bootstrap wheel when the VM virtual environment lacks pip.' >&2
    exit 1
  fi

  echo "Installing pip in $app_dir/.venv."
  if ! PYTHONPATH="$1" "$venv_python" -m pip --isolated --disable-pip-version-check \
    install --no-index --no-deps --ignore-installed "$1"; then
    echo "Could not install pip in $app_dir/.venv. Check that the SSH deploy user can write to it." >&2
    exit 1
  fi
fi

rm -rf -- "$release_dir/pip-bootstrap"

install_dependencies() {
  "$venv_python" -m pip --disable-pip-version-check install -r "$1/requirements.txt"
}

activate_access_env() {
  if [ -f "$env_file" ]; then
    install -m 600 "$env_file" "$previous_env" || return 1
  fi
  mv -Tf -- "$release_dir/.env" "$env_file" || return 1
  env_replaced=yes
}

start_release() {
  ln -sfn -- "$1" "$app_dir/current.next" &&
    mv -Tf -- "$app_dir/current.next" "$current" &&
    sudo -n "$systemctl" restart "$service"
}

wait_for_app() {
  attempt=0
  while [ "$attempt" -lt 15 ]; do
    if curl --noproxy '*' -fs --max-time 2 http://127.0.0.1:8000/health >/dev/null &&
      "$systemctl" is-active --quiet "$service"; then
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
elif activate_access_env && start_release "$release_dir" && wait_for_app &&
  [ "$(curl --noproxy '*' -s --max-time 2 -o /dev/null -w '%{http_code}' \
    http://127.0.0.1:8000/api/tickets)" = 401 ]; then
  rm -f -- "$previous_env"
  echo 'Deployment healthy on port 8000.'
  exit 0
else
  echo 'Deployment failed its startup checks.' >&2
  "$systemctl" status "$service" --no-pager --lines=15 >&2 || true
fi

if [ "$env_replaced" = yes ]; then
  if [ -f "$previous_env" ]; then
    mv -Tf -- "$previous_env" "$env_file"
  else
    rm -f -- "$env_file"
  fi
else
  rm -f -- "$previous_env"
fi

if [ -n "$previous_release" ]; then
  install_dependencies "$previous_release" || echo 'Could not reinstall the previous requirements.' >&2
  if start_release "$previous_release" && wait_for_app; then
    echo 'Previous release restored.' >&2
  else
    echo 'Could not restore the previous release.' >&2
  fi
elif [ "$(readlink "$current" || true)" = "$release_dir" ]; then
  sudo -n "$systemctl" stop "$service"
  rm -- "$current"
fi
exit 1
