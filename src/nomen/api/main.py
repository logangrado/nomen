import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from starlette.middleware.sessions import SessionMiddleware

from nomen.api.deps import _RedirectException
from nomen.api.routes import matches, name_detail, names, ratings, user


def create_app() -> FastAPI:
    app = FastAPI(title="Nomen")

    secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")
    app.add_middleware(SessionMiddleware, secret_key=secret_key)

    app.include_router(user.router)
    app.include_router(names.router)
    app.include_router(name_detail.router)
    app.include_router(ratings.router)
    app.include_router(matches.router)

    @app.exception_handler(_RedirectException)
    async def redirect_exception_handler(request: Request, exc: _RedirectException):
        return RedirectResponse(url=exc.url)

    return app


app = create_app()
