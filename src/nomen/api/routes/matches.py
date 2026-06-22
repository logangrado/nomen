from pathlib import Path

from fastapi import APIRouter, Depends, Query, Request
from fastapi.templating import Jinja2Templates

from nomen.api.config import get_config
from nomen.api.deps import get_db, require_user
from nomen.queries import get_matches, get_user_ratings

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")

RATING_ORDER = [2, 1, -1, -2]
RATING_LABELS = {2: "Love", 1: "Like", -1: "Dislike", -2: "Definitely not"}


@router.get("/matches")
async def matches_page(
    request: Request,
    user_id: str = Depends(require_user),
    conn=Depends(get_db),
):
    config = get_config()
    other = config.user2 if user_id == config.user1 else config.user1
    matches = get_matches(conn, user_id, other)
    return templates.TemplateResponse(
        request,
        "matches.html",
        {"matches": matches, "user_id": user_id, "other": other, "rating_labels": RATING_LABELS},
    )


@router.get("/me/ratings")
async def my_ratings_page(
    request: Request,
    user_id: str = Depends(require_user),
    conn=Depends(get_db),
    rating: int | None = Query(default=None),
):
    ratings = get_user_ratings(conn, user_id, rating=rating)
    # Group by rating value for display
    grouped: dict[str, list] = {r: [] for r in RATING_ORDER}
    for row in ratings:
        grouped[row["rating"]].append(row)

    return templates.TemplateResponse(
        request,
        "my_ratings.html",
        {
            "grouped": grouped,
            "active_rating": rating,
            "user_id": user_id,
            "rating_order": RATING_ORDER,
            "rating_labels": RATING_LABELS,
        },
    )
