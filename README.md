# Support ticket queue

A full-stack interview starter. The React frontend lists support tickets and lets users create new ones. FastAPI serves the API, and SQLite stores tickets between restarts. The database starts with three sample tickets, including an open and a resolved ticket.

## Run locally

Use Python 3.12 and Node.js 24 to match CI. From the repository root, start FastAPI in one terminal.

```sh
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

In a second terminal, start the React development server.

```sh
cd frontend
npm ci
npm run dev
```

Open [the ticket queue](http://127.0.0.1:5173) or [the API documentation](http://127.0.0.1:8000/docs). Vite forwards `/api` requests to FastAPI on port `8000`. The database defaults to `backend/data/tickets.sqlite3` when started as shown, and `TICKET_DB_PATH` overrides its location.

## Run tests

Run the frontend tests from the repository root.

```sh
npm --prefix frontend ci
npm --prefix frontend test
```

Run the backend tests with the virtual environment active.

```sh
cd backend
python -m pip install -r requirements-test.txt
python -m pytest -q
```

The frontend suite simulates API responses. The backend suite uses a temporary SQLite database. Both run without starting development servers.

## Starter code

| Path | Purpose |
| --- | --- |
| `backend/app/main.py` | FastAPI routes and request validation |
| `backend/app/database.py` | SQLite connection, schema, and sample tickets |
| `frontend/src/App.jsx` | React ticket list and creation form |

| Endpoint | Behavior |
| --- | --- |
| `GET /api/tickets` | Return tickets, newest first |
| `POST /api/tickets` | Accept `subject` and `description` and return the created ticket with status `open` |
| `GET /health` | Return `{"status":"ok"}` when the app is running |

## Deploy to the interview environment

Merging a pull request into `main` automatically runs the deployment workflows for the components it changes in the `devlab` GitHub environment. Direct pushes to `main` use the same path filters. When both components change, both workflows run.

| Changed code | Workflow | VM destination |
| --- | --- | --- |
| `frontend/**` | **Deploy frontend** runs the React tests, then builds and publishes the static files | `/var/www/devlab/` |
| `backend/**` | **Deploy backend** runs the FastAPI tests, then releases the Python service | `/srv/devlab/` |

Edits to a workflow file run that workflow. Edits to `.github/scripts/ssh-deploy.sh` run both because they share the SSH connection setup. You can also select a branch and run either workflow manually from the **Actions** tab once the workflow is on the default branch. [GitHub workflow triggers](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow)

### Prepare the VM once

Use a Linux VM with systemd, `curl`, `rsync`, and a Python 3.12 virtual environment at `/srv/devlab/.venv`. The backend workflow installs pip from a bundled wheel if the environment needs it. The VM needs outbound access to PyPI for runtime dependencies and must be reachable from the GitHub Actions runner over SSH on port `22`. The SSH account needs write access to `/var/www/devlab/`, `/srv/devlab/`, and the virtual environment. The VM's web server needs read access to the frontend files and permission to traverse `/var/www/devlab/`. Install the public half of `DEPLOY_SSH_KEY` in the deploy user's `~/.ssh/authorized_keys`.

On the VM, run the installer from a trusted checkout of this version before merging the deployment changes into `main`. It installs and enables the system-wide unit, which runs FastAPI as `deploy`. It grants the `deploy` account passwordless sudo to restart or stop this specific unit. The unit file and sudoers rule are owned by root.

```sh
sudo sh backend/deploy/install-system-service.sh
```

For an existing deployment, the installer stops the legacy `deploy` user service and starts the system service with the current release. It restores the legacy service if the new service fails its checks. On a fresh VM, the first backend deployment starts the system service. After migration, `devlab` can check the service with `systemctl status support-ticket-queue.service --no-pager`.

The backend listens on `127.0.0.1:8000`. Configure the VM's web server to serve `/var/www/devlab/` and forward `/api/` to FastAPI with the original request path. For Nginx, use these directives in the site's `server` block.

```nginx
root /var/www/devlab;
index index.html;

location / {
    try_files $uri $uri/ =404;
}

location = /index.html {
    add_header Cache-Control "no-cache";
}

location ^~ /api/ {
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
}
```

### GitHub environment values

The `devlab` GitHub environment supplies these values.

| Name | Stored as | Expected value |
| --- | --- | --- |
| `DEPLOY_HOST` | Secret | The VM hostname or IP address used for SSH |
| `DEPLOY_USER` | Secret | `deploy`, the SSH and FastAPI service account on the VM |
| `DEPLOY_SSH_KEY` | Secret | The multiline private SSH key for that account, usable without an interactive passphrase |
| `DEPLOY_KNOWN_HOSTS` | Variable | The verified `known_hosts` entry matching `DEPLOY_HOST`. Hashed entries work. |

The backend workflow installs runtime dependencies into `/srv/devlab/.venv`. After restarting the system service, it checks `/health` and `/api/tickets`. If deployment fails, it reapplies the previous release's requirements and restarts that release. The SQLite database lives at `/srv/devlab/data/tickets.sqlite3` across releases. To inspect the service logs on the VM, run `sudo journalctl -u support-ticket-queue.service -n 50 --no-pager`. Open the site's web URL and create a test ticket to verify both deployments together.

## Candidate exercise

Add a **Resolve** button to open tickets. When someone clicks it, save the new status through FastAPI and show the ticket as **Resolved**. The button should only appear on open tickets. If the update fails, show an error and keep the ticket open in the UI.

Deploy your change to the provided interview environment. At the deployed URL, resolve an open ticket and refresh the page to verify that the change persists. Share the deployed URL and walk through how the request moves from the button to the database.
