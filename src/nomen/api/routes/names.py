from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from fastapi.templating import Jinja2Templates

from nomen.api.deps import get_db, require_user
from nomen.queries import get_language_tags, random_name, search_names

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")

PAGE_SIZE = 200


def _filter_params(
    gender: str | None = Query(default=None),
    tags: list[str] = Query(default=[]),
    hide_rated: bool = Query(default=False),
):
    return {"gender": gender, "tags": tags, "hide_rated": hide_rated}


@router.get("/")
async def browse(
    request: Request,
    user_id: str = Depends(require_user),
    conn=Depends(get_db),
    gender: str | None = Query(default=None),
    tags: list[str] = Query(default=[]),
    hide_rated: bool = Query(default=False),
    search: str | None = Query(default=None),
    popularity_min: float | None = Query(default=None),
    popularity_max: float | None = Query(default=None),
    trend: str | None = Query(default=None),
):
    all_tags = get_language_tags(conn)
    names = search_names(
        conn,
        gender=gender or None,
        language_tags=tags or None,
        hide_rated_by=user_id if hide_rated else None,
        current_user=user_id,
        search=search or None,
        popularity_min=popularity_min,
        popularity_max=popularity_max,
        trend=trend or None,
        limit=PAGE_SIZE,
    )

    truncated = len(names) == PAGE_SIZE
    is_htmx = request.headers.get("HX-Request") == "true"
    template = "partials/name_list.html" if is_htmx else "browse.html"

    return templates.TemplateResponse(
        request,
        template,
        {
            "names": names,
            "all_tags": all_tags,
            "gender": gender,
            "tags": tags,
            "hide_rated": hide_rated,
            "search": search or "",
            "popularity_min": popularity_min,
            "popularity_max": popularity_max,
            "trend": trend or "",
            "truncated": truncated,
            "user_id": user_id,
        },
    )


@router.get("/names")
async def names_fragment(
    request: Request,
    user_id: str = Depends(require_user),
    conn=Depends(get_db),
    gender: str | None = Query(default=None),
    tags: list[str] = Query(default=[]),
    hide_rated: bool = Query(default=False),
    search: str | None = Query(default=None),
    popularity_min: float | None = Query(default=None),
    popularity_max: float | None = Query(default=None),
    trend: str | None = Query(default=None),
):
    names = search_names(
        conn,
        gender=gender or None,
        language_tags=tags or None,
        hide_rated_by=user_id if hide_rated else None,
        current_user=user_id,
        search=search or None,
        popularity_min=popularity_min,
        popularity_max=popularity_max,
        trend=trend or None,
        limit=PAGE_SIZE,
    )
    truncated = len(names) == PAGE_SIZE
    return templates.TemplateResponse(
        request,
        "partials/name_list.html",
        {
            "names": names,
            "gender": gender,
            "tags": tags,
            "hide_rated": hide_rated,
            "search": search or "",
            "popularity_min": popularity_min,
            "popularity_max": popularity_max,
            "trend": trend or "",
            "truncated": truncated,
            "user_id": user_id,
        },
    )


@router.get("/random")
async def random_page(
    request: Request,
    user_id: str = Depends(require_user),
    conn=Depends(get_db),
    gender: str | None = Query(default=None),
    tags: list[str] = Query(default=[]),
    hide_rated: bool = Query(default=False),
):
    all_tags = get_language_tags(conn)
    name = random_name(
        conn,
        gender=gender or None,
        language_tags=tags or None,
        hide_rated_by=user_id if hide_rated else None,
        current_user=user_id,
    )
    return templates.TemplateResponse(
        request,
        "random.html",
        {
            "name": name,
            "all_tags": all_tags,
            "gender": gender,
            "tags": tags,
            "hide_rated": hide_rated,
            "user_id": user_id,
        },
    )


@router.get("/random/next")
async def random_next(
    request: Request,
    user_id: str = Depends(require_user),
    conn=Depends(get_db),
    gender: str | None = Query(default=None),
    tags: list[str] = Query(default=[]),
    hide_rated: bool = Query(default=False),
):
    name = random_name(
        conn,
        gender=gender or None,
        language_tags=tags or None,
        hide_rated_by=user_id if hide_rated else None,
        current_user=user_id,
    )
    return templates.TemplateResponse(
        request,
        "partials/name_card.html",
        {"name": name, "gender": gender, "tags": tags, "hide_rated": hide_rated, "user_id": user_id},
    )
