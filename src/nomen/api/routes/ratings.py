from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from nomen.api.deps import get_db, require_user
from nomen.queries import delete_rating, get_name_for_card, upsert_rating

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")


@router.post("/rate")
async def rate(
    request: Request,
    name: str = Form(...),
    rating: int = Form(...),
    mode: str = Form(default="browse"),  # "browse" or "random"
    gender: str | None = Form(default=None),
    tags: list[str] = Form(default=[]),
    hide_rated: bool = Form(default=False),
    user_id: str = Depends(require_user),
    conn=Depends(get_db),
):
    if rating not in (2, 1, -1, -2):
        return HTMLResponse("Invalid rating", status_code=400)

    upsert_rating(conn, name, user_id, rating)

    response = templates.TemplateResponse(
        request,
        "partials/rating_buttons.html",
        {
            "name": name,
            "user_rating": rating,
            "mode": mode,
            "gender": gender,
            "tags": tags,
            "hide_rated": hide_rated,
        },
    )

    if mode == "random":
        # Signal htmx to load next card after successful rating
        response.headers["HX-Trigger"] = "rated"

    return response


@router.post("/random/undo")
async def random_undo(
    request: Request,
    name: str = Form(...),
    prev_rating: str = Form(default=""),
    user_id: str = Depends(require_user),
    conn=Depends(get_db),
):
    """Undo the last rating and return the card for that name."""
    if prev_rating:
        try:
            upsert_rating(conn, name, user_id, int(prev_rating))
        except ValueError:
            delete_rating(conn, name, user_id)
    else:
        delete_rating(conn, name, user_id)

    name_data = get_name_for_card(conn, name, user_id)
    return templates.TemplateResponse(
        request,
        "partials/name_card.html",
        {"name": name_data, "gender": None, "tags": [], "hide_rated": False, "conditions": "", "user_id": user_id},
    )
