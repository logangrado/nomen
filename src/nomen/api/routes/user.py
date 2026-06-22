from pathlib import Path

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from nomen.api.config import get_config

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")


@router.get("/user/select")
async def user_select_page(request: Request):
    config = get_config()
    return templates.TemplateResponse(
        request, "user_select.html", {"config": config}
    )


@router.post("/user/select")
async def user_select_submit(request: Request, user_id: str = Form(...)):
    config = get_config()
    if user_id not in (config.user1, config.user2):
        return RedirectResponse(url="/user/select", status_code=303)
    request.session["user_id"] = user_id
    return RedirectResponse(url="/", status_code=303)


@router.get("/user/logout")
async def user_logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/user/select", status_code=303)
