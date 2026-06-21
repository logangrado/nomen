"""Behind the Name (behindthename.com) scraper pipeline.

Scrapes name listings by letter (A-Z), extracting:
  - name
  - gender
  - usage/language tags
  - description/etymology

Data is stored in the `names` and `name_meta` tables.

Rate limit: 1 request/second (site allows 2/sec; we stay conservative).
"""
import re
import string
import time
import os
from typing import Iterator
from urllib.parse import unquote

import httpx
import psycopg
from bs4 import BeautifulSoup

from nomen.pipelines.base import normalize_name

BASE_URL = "https://www.behindthename.com"
RATE_LIMIT_SECONDS = 1.0

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; nomen-pipeline/1.0; personal use)"}


# ---------------------------------------------------------------------------
# Fetching
# ---------------------------------------------------------------------------

def _get(client: httpx.Client, url: str) -> BeautifulSoup:
    resp = client.get(url, headers=HEADERS)
    resp.raise_for_status()
    time.sleep(RATE_LIMIT_SECONDS)
    return BeautifulSoup(resp.text, "html.parser")


def _last_page(soup: BeautifulSoup) -> int:
    """Return the total number of pages for a letter listing."""
    # Pagination links: /names/letter/a/2, /names/letter/a/3, ...
    page_links = soup.select("a[href*='/names/letter/']")
    pages = []
    for a in page_links:
        parts = a["href"].rstrip("/").split("/")
        if parts[-1].isdigit():
            pages.append(int(parts[-1]))
    return max(pages, default=1)


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def _parse_gender(gender_span) -> str | None:
    """Return 'M', 'F', 'MF', or None from a listgender span."""
    if not gender_span:
        return None
    inners = gender_span.find_all("span")
    titles = {s.get("title", "").lower() for s in inners}
    if "masculine" in titles and "feminine" in titles:
        return "MF"
    if "masculine" in titles:
        return "M"
    if "feminine" in titles:
        return "F"
    return None


def _parse_description(name_span) -> str:
    """Extract description text following the <br> after a name entry.

    Strips citation reference spans (<span class="cit-grp">).
    """
    # Walk forward from the listusage span to collect description text
    usage_span = name_span.find_next_sibling("span", class_="listusage")
    if not usage_span:
        return ""

    br = usage_span.find_next_sibling("br")
    if not br:
        return ""

    parts = []
    for node in br.next_siblings:
        # Stop at the next name entry
        if hasattr(node, "attrs") and "listname" in node.get("class", []):
            break
        # Skip citation refs
        if hasattr(node, "attrs") and "cit-grp" in node.get("class", []):
            continue
        if isinstance(node, str):
            parts.append(node)
        else:
            # Get text from inline elements (links to elements, names, etc.)
            # but skip cit-grp inside them
            for cit in node.find_all("span", class_="cit-grp"):
                cit.decompose()
            parts.append(node.get_text())

    return " ".join(parts).split(".")[0].strip()  # first sentence as meaning


def _parse_page(soup: BeautifulSoup) -> Iterator[dict]:
    """Yield one dict per name entry on the page."""
    for name_span in soup.find_all("span", class_="listname"):
        a = name_span.find("a", class_="nll")
        if not a:
            continue

        # btn_id: slug from href, cleaned to ASCII alphanumerics and hyphens
        raw_slug = unquote(a["href"].rstrip("/").split("/")[-1])
        btn_id = re.sub(r"[^a-z0-9-]", "", raw_slug.lower())

        # name: use the display text, not the slug — handles names like "Abd ar-Rashid"
        # Strip the trailing " 1", " 2" disambiguation suffix BTN adds to display names
        display = a.get_text().strip()
        display = re.sub(r"\s+\d+$", "", display)
        name = normalize_name(display)

        gender_span = name_span.find_next_sibling("span", class_="listgender")
        gender = _parse_gender(gender_span)

        usage_span = name_span.find_next_sibling("span", class_="listusage")
        usage_tags = []
        if usage_span:
            raw_tags = [a.get_text() for a in usage_span.find_all("a", class_="usg")]
            # Strip qualifiers like "(Rare)", "(Archaic)", "(Modern)", "(Medieval)", etc.
            usage_tags = list(dict.fromkeys(
                re.sub(r"\s*\(.*?\)", "", tag).strip() for tag in raw_tags
            ))

        description = _parse_description(name_span)

        yield {
            "btn_id": btn_id,
            "name": name,
            "gender": gender,
            "usage_tags": usage_tags,
            "meaning": description or None,
        }



# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

def _upsert_name_meta(conn: psycopg.Connection, record: dict) -> None:
    conn.execute(
        "INSERT INTO names (name) VALUES (%s) ON CONFLICT (name) DO NOTHING",
        (record["name"],),
    )
    conn.execute(
        """
        INSERT INTO name_meta (btn_id, name, language_tags, meaning, gender)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (btn_id) DO UPDATE SET
            name = EXCLUDED.name,
            language_tags = EXCLUDED.language_tags,
            meaning = EXCLUDED.meaning,
            gender = EXCLUDED.gender
        """,
        (
            record["btn_id"],
            record["name"],
            record["usage_tags"] or None,
            record["meaning"],
            record["gender"],
        ),
    )


def load_btn(letters: str | None = None) -> None:
    """Scrape Behind the Name and load into name_meta.

    Args:
        letters: string of letters to scrape, e.g. "abc". Defaults to all A-Z.
    """
    targets = letters.lower() if letters else string.ascii_lowercase
    db_url = os.environ["DATABASE_URL"]

    with httpx.Client(timeout=30) as client, psycopg.connect(db_url) as conn:
        for letter in targets:
            url = f"{BASE_URL}/names/letter/{letter}"
            print(f"Fetching {url} ...", flush=True)
            soup = _get(client, url)

            total_pages = _last_page(soup)
            print(f"  {letter.upper()}: {total_pages} page(s)", flush=True)

            pages = [soup] + [
                _get(client, f"{BASE_URL}/names/letter/{letter}/{p}")
                for p in range(2, total_pages + 1)
            ]

            count = 0
            for page_soup in pages:
                for record in _parse_page(page_soup):
                    _upsert_name_meta(conn, record)
                    count += 1

            conn.commit()
            print(f"  {letter.upper()}: {count} names loaded", flush=True)

    print("Done.")
