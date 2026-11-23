# Support ticket queue interview tasks

You have 60 minutes to configure HTTPS, ship a small feature, and diagnose a lab incident. For each task, show how you verified the result and explain what you observed.

## Before you start

Confirm your VM access, lab token, and deployment branch with your interviewer. The lab starts over HTTP. Open the queue and use the supplied token to check that it loads before you make changes. [HTTP lab](http://devlab.labs.akamaicentral.com/)

Use the README for local setup, test commands, GitHub Actions, and VM health checks. [Project README](README.md)

## 1. Enable HTTPS

Configure the port 443 virtual host in Apache’s `devlab.conf` for `devlab.labs.akamaicentral.com`. The HTTPS site must serve the React page and route `/api/` requests to the existing FastAPI service. Use the existing Let’s Encrypt files.

- Certificate bundle at `/etc/letsencrypt/live/devlab.labs.akamaicentral.com/fullchain.pem`
- Private key at `/etc/letsencrypt/live/devlab.labs.akamaicentral.com/privkey.pem`

### What to demonstrate

1. Validate the Apache configuration before reloading it. Show the validation result.
2. Open the HTTPS lab and show that it loads with a trusted certificate. [HTTPS lab](https://devlab.labs.akamaicentral.com/)
3. Enter the supplied token over HTTPS. Show that the queue displays tickets and that `GET /api/tickets` returns `200 OK` with the ticket list.

## 2. Add a Resolve action

The queue already lists tickets and lets users create them. Add a way to resolve an open ticket from the list. Implement the change in React and FastAPI using the existing token access and SQLite database.

Before you start implementing the Resolve action, create a feature branch from `dev`. Make your code changes on that branch. Once you’re satisfied with the results, open a pull request to merge your feature branch into `dev`.

### Expected behavior

- Only open tickets show a **Resolve** button. Clicking it sends a request to FastAPI to update that ticket.
- FastAPI saves the new status in SQLite. After the API confirms success, the ticket shows **Resolved** and its button disappears. Refreshing the page still shows it as resolved.
- If the request fails, the ticket still shows **Open** and the page displays an error.

### What to demonstrate

1. Run the existing frontend and backend tests. If time allows, add a focused regression test for the new behavior.
2. Deploy both components through GitHub Actions from the agreed branch and show the successful workflow runs for your changes. [CI and deployment instructions](README.md#ci-and-deployment)
3. Create a test ticket in the deployed queue, resolve it, and refresh the page to show that the status persists. Explain how you checked the failure case.

## 3. Diagnose and fix a broken queue

When your interviewer starts the incident, the lab page will open and display “Couldn’t load the ticket queue.” Investigate the fault on the lab VM and restore the queue.

### What to demonstrate

1. Reproduce the error and identify which browser request fails. Note its URL and response status.
2. Use the evidence from your checks to narrow down where the request fails. Explain what the evidence tells you and identify the root cause.
3. Make the smallest change that addresses the cause. Verify that the same request returns `200 OK` with the ticket list and that the queue displays tickets after a refresh.
4. In the debrief, summarize what broke, what you changed, and which check confirmed recovery.
