import json
from collections import defaultdict
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from nomen.api.deps import get_db, require_user
from nomen.queries import get_name_detail, get_name_stats, get_user_ratings, upsert_rating

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")


def _build_chart_data(stats: list[dict]) -> str:
    """Convert flat stats rows into Chart.js dataset JSON."""
    by_gender: dict[str, dict[int, float]] = defaultdict(dict)
    for row in stats:
        by_gender[row["gender"]][row["year"]] = float(row["rate_per_1000"])

    all_years = sorted({row["year"] for row in stats})

    colors = {"F": "#e05c8a", "M": "#4a90d9"}
    datasets = []
    for gender in sorted(by_gender):
        counts = by_gender[gender]
        datasets.append({
            "label": gender,
            "data": [counts.get(y, 0) for y in all_years],
            "borderColor": colors.get(gender, "#888"),
            "backgroundColor": colors.get(gender, "#888") + "22",
            "fill": False,
            "tension": 0.3,
            "pointRadius": 0,
            "borderWidth": 2,
        })

    return json.dumps({"labels": all_years, "datasets": datasets})


@router.get("/names/{name}")
async def name_detail(
    request: Request,
    name: str,
    user_id: str = Depends(require_user),
    conn=Depends(get_db),
):
    detail = get_name_detail(conn, name)
    if detail is None:
        return HTMLResponse("Name not found", status_code=404)

    stats = get_name_stats(conn, name)
    chart_data = _build_chart_data(stats) if stats else None

    # Current user's rating for this name
    ratings = get_user_ratings(conn, user_id)
    user_rating = next((r["rating"] for r in ratings if r["name"] == name), None)

    return templates.TemplateResponse(
        request,
        "name_detail.html",
        {
            "detail": detail,
            "chart_data": chart_data,
            "user_id": user_id,
            "user_rating": user_rating,
            "name": name,
        },
    )
