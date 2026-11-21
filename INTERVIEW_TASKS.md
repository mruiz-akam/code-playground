# Support ticket queue interview tasks

During the 60-minute interview, you’ll configure HTTPS, deploy a small feature, and investigate an incident in the lab. Your interviewer will provide the access token, VM access, and the branch to deploy. The [README](README.md) covers local setup, tests, deployment, and backend checks.

## 1. Enable HTTPS

Configure Apache’s `devlab.conf` on the lab VM to serve the ticket queue for `devlab.labs.akamaicentral.com` on port 443. Use the existing Let’s Encrypt files.

- Certificate bundle at `/etc/letsencrypt/live/devlab.labs.akamaicentral.com/fullchain.pem`
- Private key at `/etc/letsencrypt/live/devlab.labs.akamaicentral.com/privkey.pem`

Validate the Apache configuration before applying it. Show that the browser trusts the certificate and that, after you enter the lab token, `GET /api/tickets` returns `200 OK` with the ticket list over HTTPS. [HTTPS lab](https://devlab.labs.akamaicentral.com/)

## 2. Add a Resolve action

Let a user resolve an open support ticket from the queue. Make the change in React and FastAPI.

- Show a **Resolve** button on open tickets. Once a ticket is resolved, show its **Resolved** status and remove the button.
- Save the new status to SQLite through the API. Update the page after the request succeeds, and verify that the ticket stays resolved after a refresh.
- If the request fails, keep the ticket open in the UI and show an error.

Run the existing frontend and backend tests. Deploy both components through GitHub Actions from the agreed branch and demonstrate the change on a test ticket in the lab. If time allows, add a focused regression test.

## 3. Diagnose and fix a broken queue

Your interviewer will introduce a fault. The page will open, but the queue will display “Couldn’t load the ticket queue.”

Reproduce the problem and talk through what each check tells you. Identify the root cause, make the smallest change that restores the queue, and verify that the API returns the ticket list and the browser displays it again. In the debrief, point to the evidence that confirmed your diagnosis and the fix.
