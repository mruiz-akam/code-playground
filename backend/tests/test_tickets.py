from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

import app.access as access
from app.main import app

ACCESS_TOKEN = "test-lab-access-token"
HTTPS_URL = "https://testserver"


@pytest.fixture
def access_env(tmp_path, monkeypatch):
    path = tmp_path / ".env"
    path.write_text(f"DEVLAB_ACCESS_TOKEN={ACCESS_TOKEN}\n")
    monkeypatch.setenv("DEVLAB_ENV_FILE", str(path))
    monkeypatch.delenv("DEVLAB_ALLOW_HTTP", raising=False)
    return path


@pytest.fixture
def database_path(tmp_path, monkeypatch):
    path = tmp_path / "tickets.sqlite3"
    monkeypatch.setenv("TICKET_DB_PATH", str(path))
    return path


@pytest.fixture
def client(database_path, access_env):
    with TestClient(app, base_url=HTTPS_URL) as client:
        assert client.post("/api/access", json={"token": ACCESS_TOKEN}).status_code == 204
        yield client


def test_health(database_path, access_env):
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_lists_seeded_tickets_newest_first(client):
    response = client.get("/api/tickets")

    assert response.status_code == 200
    tickets = response.json()
    assert len(tickets) == 3
    assert {ticket["status"] for ticket in tickets} == {"open", "resolved"}
    ids = [ticket["id"] for ticket in tickets]
    assert ids == sorted(ids, reverse=True)


def test_creates_an_open_ticket_and_keeps_it_after_restart(database_path, access_env):
    with TestClient(app, base_url=HTTPS_URL) as client:
        assert client.post("/api/access", json={"token": ACCESS_TOKEN}).status_code == 204
        session = client.cookies["devlab_session"]
        initial_tickets = client.get("/api/tickets").json()
        response = client.post(
            "/api/tickets",
            json={"subject": "  Cannot open a report  ", "description": "  Reports time out.  "},
        )

        assert response.status_code == 201
        ticket = response.json()
        assert ticket["subject"] == "Cannot open a report"
        assert ticket["description"] == "Reports time out."
        assert ticket["status"] == "open"
        assert datetime.fromisoformat(ticket["created_at"]).utcoffset() == timedelta(0)
        assert client.get("/api/tickets").json() == [ticket, *initial_tickets]

    with TestClient(app, base_url=HTTPS_URL) as restarted_client:
        restarted_client.cookies.set("devlab_session", session)
        assert restarted_client.get("/api/tickets").json() == [ticket, *initial_tickets]


def test_tickets_require_access(database_path, access_env):
    with TestClient(app, base_url=HTTPS_URL) as client:
        assert client.get("/api/tickets").status_code == 401
        response = client.post("/api/tickets", json={"subject": "Test", "description": "Details"})
        assert response.status_code == 401


def test_token_opens_a_secure_session(database_path, access_env):
    with TestClient(app, base_url=HTTPS_URL) as client:
        wrong = client.post("/api/access", json={"token": "wrong-token"})
        assert wrong.status_code == 401
        assert not client.cookies

        allowed = client.post("/api/access", json={"token": ACCESS_TOKEN})
        assert allowed.status_code == 204
        cookie = allowed.headers["set-cookie"]
        assert all(attribute in cookie for attribute in ("Secure", "HttpOnly", "SameSite=strict"))
        assert ACCESS_TOKEN not in cookie
        assert client.get("/api/tickets").status_code == 200


def test_token_requires_https(database_path, access_env):
    with TestClient(app) as client:
        assert client.get("/api/tickets").headers["X-Devlab-Allow-Http"] == "0"
        assert client.post("/api/access", json={"token": ACCESS_TOKEN}).status_code == 403
        assert not client.cookies


def test_local_http_access(database_path, access_env, monkeypatch):
    monkeypatch.setenv("DEVLAB_ALLOW_HTTP", "1")
    with TestClient(app) as client:
        assert client.post("/api/access", json={"token": ACCESS_TOKEN}).status_code == 204
        assert client.get("/api/tickets").status_code == 200


def test_lab_http_session_is_separate_from_https(database_path, access_env):
    access_env.write_text(f"DEVLAB_ACCESS_TOKEN={ACCESS_TOKEN}\nDEVLAB_ALLOW_HTTP=1\n")
    with TestClient(app) as client:
        assert client.get("/api/tickets").headers["X-Devlab-Allow-Http"] == "1"
        allowed = client.post("/api/access", json={"token": ACCESS_TOKEN})
        assert allowed.status_code == 204
        assert "Secure" not in allowed.headers["set-cookie"]
        assert client.get("/api/tickets").status_code == 200
        http_session = client.cookies["devlab_http_session"]

    with TestClient(app, base_url=HTTPS_URL) as client:
        assert client.get("/api/tickets", headers={"Cookie": f"devlab_session={http_session}"}).status_code == 401
        allowed = client.post("/api/access", json={"token": ACCESS_TOKEN})
        assert allowed.status_code == 204
        assert "Secure" in allowed.headers["set-cookie"]
        assert client.get("/api/tickets").status_code == 200


def test_missing_access_token_prevents_startup(database_path, access_env):
    access_env.write_text("")
    with pytest.raises(RuntimeError, match="Set DEVLAB_ACCESS_TOKEN"), TestClient(app):
        pass


def test_rejects_ticket_writes_from_another_origin(client):
    response = client.post(
        "/api/tickets",
        json={"subject": "Test", "description": "Details"},
        headers={"Origin": "https://another-site.example"},
    )
    assert response.status_code == 403


def test_expired_session_requires_a_new_token(client, monkeypatch):
    later = access.time() + access.SESSION_SECONDS + 1
    monkeypatch.setattr(access, "time", lambda: later)
    assert client.get("/api/tickets").status_code == 401


def test_rotating_the_token_revokes_the_previous_session(database_path, access_env):
    with TestClient(app, base_url=HTTPS_URL) as client:
        assert client.post("/api/access", json={"token": ACCESS_TOKEN}).status_code == 204
        previous_session = client.cookies["devlab_session"]

    access_env.write_text("DEVLAB_ACCESS_TOKEN=rotated-test-token\n")
    with TestClient(app, base_url=HTTPS_URL) as client:
        client.cookies.set("devlab_session", previous_session)
        assert client.get("/api/tickets").status_code == 401


@pytest.mark.parametrize(
    ("payload", "field"),
    [
        ({"description": "Details"}, "subject"),
        ({"subject": "Report failed"}, "description"),
        ({"subject": "   ", "description": "Details"}, "subject"),
        ({"subject": "Report failed", "description": "   "}, "description"),
        ({"subject": "x" * 121, "description": "Details"}, "subject"),
        ({"subject": "Report failed", "description": "x" * 2001}, "description"),
    ],
    ids=[
        "missing-subject",
        "missing-description",
        "blank-subject",
        "blank-description",
        "long-subject",
        "long-description",
    ],
)
def test_rejects_invalid_tickets_without_saving_them(client, payload, field):
    initial_tickets = client.get("/api/tickets").json()

    response = client.post("/api/tickets", json=payload)

    assert response.status_code == 422
    assert ["body", field] in [error["loc"] for error in response.json()["detail"]]
    assert client.get("/api/tickets").json() == initial_tickets
