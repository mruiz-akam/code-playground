from contextlib import asynccontextmanager
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, FastAPI, Request, status
from pydantic import BaseModel, ConfigDict, Field

from app.access import load_access_settings, require_access, router as access_router
from app.database import connect, initialize


class TicketCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    subject: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=2000)


class Ticket(TicketCreate):
    id: int
    status: Literal["open", "resolved"]
    created_at: datetime


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.access = load_access_settings()
    app.state.database_path = initialize()
    yield


app = FastAPI(title="Support ticket queue", lifespan=lifespan)
app.include_router(access_router)
tickets = APIRouter(prefix="/api/tickets", dependencies=[Depends(require_access)])


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@tickets.get("", response_model=list[Ticket])
def list_tickets(request: Request):
    with connect(request.app.state.database_path) as connection:
        rows = connection.execute(
            "SELECT id, subject, description, status, created_at FROM tickets ORDER BY id DESC"
        ).fetchall()
    return [dict(row) for row in rows]


@tickets.post("", response_model=Ticket, status_code=status.HTTP_201_CREATED)
def create_ticket(ticket: TicketCreate, request: Request):
    with connect(request.app.state.database_path) as connection:
        row = connection.execute(
            """
            INSERT INTO tickets (subject, description) VALUES (?, ?)
            RETURNING id, subject, description, status, created_at
            """,
            (ticket.subject, ticket.description),
        ).fetchone()
    return dict(row)


app.include_router(tickets)
