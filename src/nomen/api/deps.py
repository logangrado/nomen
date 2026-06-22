import os
from typing import Iterator

import psycopg
from fastapi import Request
from fastapi.responses import RedirectResponse
from starlette.responses import Response

from nomen.api.config import Config, get_config


def get_db() -> Iterator[psycopg.Connection]:
    db_url = os.environ["DATABASE_URL"]
    with psycopg.connect(db_url) as conn:
        yield conn


def get_user(request: Request) -> str | None:
    return request.session.get("user_id")


def require_user(request: Request) -> str:
    """Return current user_id or raise a redirect to /user/select."""
    user_id = request.session.get("user_id")
    if not user_id:
        # Returning a redirect from a dependency raises it as an exception
        raise _RedirectException("/user/select")
    return user_id


class _RedirectException(Exception):
    def __init__(self, url: str):
        self.url = url
