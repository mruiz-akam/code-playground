import os
import sqlite3
from collections.abc import Iterator
from contextlib import closing, contextmanager
from pathlib import Path

SEED_TICKETS = (
    (
        "Password reset email never arrives",
        "I requested a reset twice this morning and checked my spam folder. "
        "Could you help me get back into my account?",
        "open",
    ),
    (
        "CSV export misses the last column",
        "The export downloaded from the Reports page is missing the Notes column.",
        "open",
    ),
    (
        "Update the billing contact",
        "Please send future invoices to our finance team. I can share the new address by reply.",
        "resolved",
    ),
)


@contextmanager
def connect(path: Path) -> Iterator[sqlite3.Connection]:
    with closing(sqlite3.connect(path)) as connection, connection:
        connection.row_factory = sqlite3.Row
        yield connection


def initialize() -> Path:
    path = Path(os.environ.get("TICKET_DB_PATH", "data/tickets.sqlite3")).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)

    with connect(path) as connection:
        # Keep table creation and seeding atomic if two processes start together.
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS tickets (
                id INTEGER PRIMARY KEY,
                subject TEXT NOT NULL,
                description TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'resolved')),
                created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
            )
            """
        )
        if connection.execute("SELECT 1 FROM tickets LIMIT 1").fetchone() is None:
            connection.executemany(
                "INSERT INTO tickets (subject, description, status) VALUES (?, ?, ?)",
                SEED_TICKETS,
            )

    return path
