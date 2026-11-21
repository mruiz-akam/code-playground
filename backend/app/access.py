import hmac
import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path
from time import time

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, SecretStr

from app.database import connect

COOKIE_NAME = "devlab_session"
HTTP_COOKIE_NAME = "devlab_http_session"
SESSION_SECONDS = 90 * 60
VM_DIRECTORY = Path("/srv/devlab")
router = APIRouter()


@dataclass(frozen=True)
class AccessSettings:
    token: bytes = field(repr=False)
    require_https: bool


def load_access_settings() -> AccessSettings:
    backend = Path(__file__).resolve().parents[1]
    on_vm = backend.is_relative_to(VM_DIRECTORY.resolve())
    default_directory = VM_DIRECTORY if on_vm else backend
    env_file = Path(os.environ.get("DEVLAB_ENV_FILE", default_directory / ".env"))
    try:
        lines = env_file.read_text(encoding="utf-8").split("\n")
    except OSError as error:
        raise RuntimeError(f"Create {env_file} with DEVLAB_ACCESS_TOKEN.") from error

    values = dict(line.split("=", 1) for line in lines if "=" in line)
    token = values.get("DEVLAB_ACCESS_TOKEN", "")
    if not token.strip():
        raise RuntimeError(f"Set DEVLAB_ACCESS_TOKEN in {env_file}.")

    allow_http = values.get("DEVLAB_ALLOW_HTTP") == "1" or (
        not on_vm and os.environ.get("DEVLAB_ALLOW_HTTP") == "1"
    )
    return AccessSettings(token=token.encode(), require_https=not allow_http)


def check_origin(request: Request) -> None:
    origin = request.headers.get("origin")
    if origin and origin != str(request.base_url).rstrip("/"):
        raise HTTPException(status_code=403, detail="Use the lab site to make this request.")


def session_hash(settings: AccessSettings, session: str, *, is_https: bool) -> str:
    # Separate HTTP sessions from HTTPS sessions. Token rotation revokes both.
    value = session if is_https else f"http:{session}"
    return hmac.new(settings.token, value.encode(), "sha256").hexdigest()


class AccessRequest(BaseModel):
    token: SecretStr


@router.post("/api/access", status_code=204)
def grant_access(body: AccessRequest, request: Request, response: Response) -> None:
    settings = request.app.state.access
    is_https = request.url.scheme == "https"
    if settings.require_https and not is_https:
        raise HTTPException(status_code=403, detail="Open the lab over HTTPS.")
    check_origin(request)
    if not hmac.compare_digest(body.token.get_secret_value().encode(), settings.token):
        raise HTTPException(status_code=401, detail="Invalid access token.")

    session = secrets.token_urlsafe(32)
    now = int(time())
    with connect(request.app.state.database_path) as connection:
        connection.execute("DELETE FROM access_sessions WHERE expires_at <= ?", (now,))
        connection.execute(
            "INSERT INTO access_sessions (session_hash, expires_at) VALUES (?, ?)",
            (session_hash(settings, session, is_https=is_https), now + SESSION_SECONDS),
        )

    response.headers["Cache-Control"] = "no-store"
    response.set_cookie(
        key=COOKIE_NAME if is_https else HTTP_COOKIE_NAME,
        value=session,
        max_age=SESSION_SECONDS,
        path="/api",
        secure=is_https,
        httponly=True,
        samesite="strict",
    )


def require_access(request: Request, response: Response) -> None:
    settings = request.app.state.access
    is_https = request.url.scheme == "https"
    session = request.cookies.get(COOKIE_NAME if is_https else HTTP_COOKIE_NAME)
    if session and (not settings.require_https or is_https):
        with connect(request.app.state.database_path) as connection:
            active = connection.execute(
                "SELECT 1 FROM access_sessions WHERE session_hash = ? AND expires_at > ?",
                (session_hash(settings, session, is_https=is_https), int(time())),
            ).fetchone()
        if active:
            check_origin(request)
            response.headers["Cache-Control"] = "no-store"
            return

    raise HTTPException(
        status_code=401,
        detail="Enter the lab access token.",
        headers={
            "Cache-Control": "no-store",
            "X-Devlab-Allow-Http": "0" if settings.require_https else "1",
        },
    )
