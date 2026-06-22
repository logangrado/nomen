import json
from pathlib import Path

from fastapi import APIRouter, Depends, Query, Request
from fastapi.templating import Jinja2Templates

from nomen.api.deps import get_db, require_user
from nomen.queries import get_language_tags, random_name, search_names

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")

PAGE_SIZE = 100


def _parse_conditions(conditions: str | None) -> list[dict]:
    if not conditions:
        return []
    try:
        data = json.loads(conditions)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, ValueError):
        return []


@router.get("/")
async def browse(
    request: Request,
    user_id: str = Depends(require_user),
    conn=Depends(get_db),
    gender: str | None = Query(default=None),
    tags: list[str] = Query(default=[]),
    hide_rated: bool = Query(default=False),
    search: str | None = Query(default=None),
    trend: str | None = Query(default=None),
    sort: str = Query(default="name"),
    dir: str = Query(default="asc"),
    page: int = Query(default=1, ge=1),
    conditions: str | None = Query(default=None),
):
    conds = _parse_conditions(conditions)
    all_tags = get_language_tags(conn)
    offset = (page - 1) * PAGE_SIZE
    names = search_names(
        conn,
        gender=gender or None,
        language_tags=tags or None,
        hide_rated_by=user_id if hide_rated else None,
        current_user=user_id,
        search=search or None,
        trend=trend or None,
        conditions_arg=conds or None,
        sort_by=sort,
        sort_dir=dir,
        limit=PAGE_SIZE,
        offset=offset,
    )

    has_next = len(names) == PAGE_SIZE
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
            "trend": trend or "",
            "sort": sort,
            "dir": dir,
            "page": page,
            "has_next": has_next,
            "conditions": conditions or "",
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
    trend: str | None = Query(default=None),
    sort: str = Query(default="name"),
    dir: str = Query(default="asc"),
    page: int = Query(default=1, ge=1),
    conditions: str | None = Query(default=None),
):
    conds = _parse_conditions(conditions)
    offset = (page - 1) * PAGE_SIZE
    names = search_names(
        conn,
        gender=gender or None,
        language_tags=tags or None,
        hide_rated_by=user_id if hide_rated else None,
        current_user=user_id,
        search=search or None,
        trend=trend or None,
        conditions_arg=conds or None,
        sort_by=sort,
        sort_dir=dir,
        limit=PAGE_SIZE,
        offset=offset,
    )
    has_next = len(names) == PAGE_SIZE
    return templates.TemplateResponse(
        request,
        "partials/name_list.html",
        {
            "names": names,
            "gender": gender,
            "tags": tags,
            "hide_rated": hide_rated,
            "search": search or "",
            "trend": trend or "",
            "sort": sort,
            "dir": dir,
            "page": page,
            "has_next": has_next,
            "conditions": conditions or "",
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
