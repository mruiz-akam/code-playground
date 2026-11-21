from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def database_path(tmp_path, monkeypatch):
    path = tmp_path / "tickets.sqlite3"
    monkeypatch.setenv("TICKET_DB_PATH", str(path))
    return path


@pytest.fixture
def client(database_path):
    with TestClient(app) as client:
        yield client


def test_health(client):
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


def test_creates_an_open_ticket_and_keeps_it_after_restart(database_path):
    with TestClient(app) as client:
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

    with TestClient(app) as restarted_client:
        assert restarted_client.get("/api/tickets").json() == [ticket, *initial_tickets]


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
