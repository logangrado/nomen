import json
from pathlib import Path

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from nomen.api.deps import get_db, require_user
from nomen.queries import TAG_GROUPS, get_language_tags, random_name, search_names

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

    return templates.TemplateResponse(
        request,
        "browse.html",
        {
            "names": names,
            "all_tags": all_tags,
            "tag_groups": list(TAG_GROUPS.keys()),
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
    # Redirect full-page requests to browse so /names?... in history still works
    if request.headers.get("HX-Request") != "true":
        return RedirectResponse(url=str(request.url).replace("/names?", "/?", 1).replace("/names", "/", 1))

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
            "tag_groups": list(TAG_GROUPS.keys()),
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
    conditions: str | None = Query(default=None),
):
    conds = _parse_conditions(conditions)
    all_tags = get_language_tags(conn)
    name = random_name(
        conn,
        gender=gender or None,
        language_tags=tags or None,
        hide_rated_by=user_id if hide_rated else None,
        current_user=user_id,
        conditions_arg=conds or None,
    )
    return templates.TemplateResponse(
        request,
        "random.html",
        {
            "name": name,
            "all_tags": all_tags,
            "tag_groups": list(TAG_GROUPS.keys()),
            "gender": gender,
            "tags": tags,
            "hide_rated": hide_rated,
            "conditions": conditions or "",
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
    conditions: str | None = Query(default=None),
):
    conds = _parse_conditions(conditions)
    name = random_name(
        conn,
        gender=gender or None,
        language_tags=tags or None,
        hide_rated_by=user_id if hide_rated else None,
        current_user=user_id,
        conditions_arg=conds or None,
    )
    return templates.TemplateResponse(
        request,
        "partials/name_card.html",
        {"name": name, "gender": gender, "tags": tags, "hide_rated": hide_rated, "conditions": conditions or "", "user_id": user_id},
    )
