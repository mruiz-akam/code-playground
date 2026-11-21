# Support ticket queue

A full-stack interview starter. The React frontend lists support tickets and lets users create new ones. FastAPI serves the API, and SQLite stores tickets between restarts. The database starts with three sample tickets, including an open and a resolved ticket.

## Run locally

Use Python 3.12 and Node.js 24 to match CI. From the repository root, start FastAPI in one terminal.

Copy the example to `backend/.env` if you’re setting up the project for the first time. Enter the sample token `local-test-token` when the local queue prompts you.

```sh
cd backend
cp -n .env.example .env
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

In a second terminal, start the React development server from the repository root.

```sh
cd frontend
npm ci
npm run dev
```

Open [the ticket queue](http://127.0.0.1:5173) or [the API documentation](http://127.0.0.1:8000/docs). Vite forwards `/api` requests to FastAPI on port `8000`. The database defaults to `backend/data/tickets.sqlite3` when started as shown, and `TICKET_DB_PATH` overrides its location.

### Run tests locally

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

## CI and deployment

GitHub Actions deploys to the `devlab` lab environment. Pushes and merges to `main` run the workflows that match the changed files. A change to both components runs both workflows.

| Changed files | Workflow | What it does |
| --- | --- | --- |
| `frontend/**` | [Deploy frontend](.github/workflows/deploy-frontend.yml) | Runs the React tests, builds the frontend, and publishes it to `/var/www/devlab/`. |
| `backend/**` | [Deploy backend](.github/workflows/deploy-backend.yml) | Runs the FastAPI tests, deploys to `/srv/devlab/`, and checks the service and API after restarting. |

For an interview branch, push your changes and open **Actions**. Choose the relevant workflow, select **Run workflow**, and choose the branch agreed with your interviewer.

Open the run for your commit to check the test and deployment results. A failing test stops deployment. After the relevant workflows succeed, verify your change using the access token provided by your interviewer. During the HTTP exercise, open [http://devlab.labs.akamaicentral.com/](http://devlab.labs.akamaicentral.com/) when HTTP access is enabled for the lab. Once HTTPS works, open [https://devlab.labs.akamaicentral.com/](https://devlab.labs.akamaicentral.com/) and enter the token there to start an HTTPS session.

## Check the backend on the VM

Connect over SSH using the account and VM hostname provided by your interviewer.

```sh
ssh YOUR_VM_USER@YOUR_VM_HOST
```

Run these commands on the VM. FastAPI listens on its loopback interface.

```sh
systemctl status support-ticket-queue.service --no-pager
curl -fsS http://127.0.0.1:8000/health
curl -sS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8000/api/tickets
```

Expect `active (running)` from systemd, `{"status":"ok"}` from the health endpoint, and HTTP `401` for the ticket request without a session. To verify ticket data, enter the token at the lab URL provided by your interviewer.

If you have sudo access, use this command to check the recent backend logs.

```sh
sudo journalctl -u support-ticket-queue.service -n 50 --no-pager
```
