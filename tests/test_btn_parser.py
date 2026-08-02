"""Tests for the Behind the Name parser (no network calls — all use inline HTML)."""

from bs4 import BeautifulSoup

from nomen.pipelines.btn import _last_page, _parse_page


def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


# ---------------------------------------------------------------------------
# Helpers to build minimal page HTML matching BTN's actual structure
# ---------------------------------------------------------------------------


def _name_entry(
    slug: str,
    display: str,
    gender_html: str,
    usage_html: str,
    description: str = "",
) -> str:
    return (
        f'<span class="listname"><a href="/name/{slug}" class="nll">{display}</a></span> '
        f'<span class="listgender">{gender_html}</span> '
        f'<span class="listusage">{usage_html}</span><br>\n'
        f"{description}\n"
    )


def _fem():
    return '<span class="fem" title="feminine">f</span>'


def _masc():
    return '<span class="masc" title="masculine">m</span>'


def _usage(*tags):
    return "".join(f'<a href="/names/usage/{t.lower()}" class="usg">{t}</a>' for t in tags)


# ---------------------------------------------------------------------------
# _last_page
# ---------------------------------------------------------------------------


def test_last_page_single():
    html = '<a href="/names/letter/a/1">1</a>'
    assert _last_page(_soup(html)) == 1


def test_last_page_multi():
    html = '<a href="/names/letter/a/2">2</a><a href="/names/letter/a/5">5</a><a href="/names/letter/a/3">3</a>'
    assert _last_page(_soup(html)) == 5


def test_last_page_no_links():
    assert _last_page(_soup("<p>nothing</p>")) == 1


# ---------------------------------------------------------------------------
# _parse_page — basic fields
# ---------------------------------------------------------------------------


def test_parse_simple_feminine():
    html = _name_entry(
        "adalgund",
        "Adalgund",
        _fem(),
        _usage("Germanic"),
        'Derived from the Old German elements <i>adal</i> "noble" and <i>gunda</i> "battle".',
    )
    rows = list(_parse_page(_soup(html)))
    assert len(rows) == 1
    r = rows[0]
    assert r["btn_id"] == "adalgund"
    assert r["name"] == "adalgund"
    assert r["gender"] == "F"
    assert r["usage_tags"] == ["Germanic"]
    assert "noble" in r["meaning"]


def test_parse_masculine():
    html = _name_entry("aaron", "Aaron", _masc(), _usage("English", "French"))
    rows = list(_parse_page(_soup(html)))
    assert rows[0]["gender"] == "M"
    assert rows[0]["usage_tags"] == ["English", "French"]


def test_parse_unisex():
    gender_html = '<span class="masc" title="masculine">m</span> &amp; <span class="fem" title="feminine">f</span>'
    html = _name_entry("awee", "Awee", gender_html, _usage("Navajo"))
    rows = list(_parse_page(_soup(html)))
    assert rows[0]["gender"] == "MF"


# ---------------------------------------------------------------------------
# _parse_page — numbering and name extraction
# ---------------------------------------------------------------------------


def test_parse_numbered_entries():
    """Multiple BTN entries for the same base name (ada-1, ada-2, ada-3)."""
    html = (
        _name_entry("ada-1", "Ada 1", _fem(), _usage("English", "German"), "Short form of Adelaide.")
        + _name_entry(
            "ada-2",
            "Ada 2",
            '<span class="fem" title="feminine">f</span> &amp; <span class="masc" title="masculine">m</span>',
            _usage("Turkish"),
            "Turkish name.",
        )
        + _name_entry("ada-3", "Ada 3", _fem(), _usage("Hebrew"), "Hebrew name.")
    )
    rows = list(_parse_page(_soup(html)))
    assert len(rows) == 3
    assert [r["btn_id"] for r in rows] == ["ada-1", "ada-2", "ada-3"]
    # All three share the same base name
    assert all(r["name"] == "ada" for r in rows)


def test_display_name_used_not_slug():
    """Names like 'Abd ar-Rashid' should come from display text, not the slug."""
    html = _name_entry("abd-ar-rashid", "Abd ar-Rashid", _masc(), _usage("Arabic"))
    rows = list(_parse_page(_soup(html)))
    assert rows[0]["name"] == "abd ar-rashid"


# ---------------------------------------------------------------------------
# _parse_page — usage tag cleaning
# ---------------------------------------------------------------------------


def test_strips_qualifiers_from_usage_tags():
    html = _name_entry("aada", "Aada", _fem(), _usage("Finnish (Rare)"))
    rows = list(_parse_page(_soup(html)))
    assert rows[0]["usage_tags"] == ["Finnish"]


def test_deduplicates_usage_tags():
    """Finnish (Rare) and Finnish on the same entry should collapse to one."""
    html = _name_entry("aada", "Aada", _fem(), _usage("Finnish (Rare)", "Finnish"))
    rows = list(_parse_page(_soup(html)))
    assert rows[0]["usage_tags"] == ["Finnish"]


def test_multiple_usage_tags():
    html = _name_entry("aage", "Aage", _masc(), _usage("Danish", "Norwegian"))
    rows = list(_parse_page(_soup(html)))
    assert rows[0]["usage_tags"] == ["Danish", "Norwegian"]


# ---------------------------------------------------------------------------
# _parse_page — citations stripped from description
# ---------------------------------------------------------------------------


def test_strips_citations_from_description():
    html = _name_entry(
        "adalgund",
        "Adalgund",
        _fem(),
        _usage("Germanic"),
        'Derived from "noble"<span class="cit-grp"><a href="#ref1" class="cit">[1]</a></span>.',
    )
    rows = list(_parse_page(_soup(html)))
    assert "[1]" not in (rows[0]["meaning"] or "")


# ---------------------------------------------------------------------------
# _parse_page — slug cleaning
# ---------------------------------------------------------------------------


def test_btn_id_cleaned_to_ascii():
    """Non-ASCII characters in the slug should be stripped."""
    html = _name_entry("abd\u02bfar-rashid", "Abd ar-Rashid", _masc(), _usage("Arabic"))
    rows = list(_parse_page(_soup(html)))
    assert rows[0]["btn_id"] == "abdar-rashid"


def test_empty_page():
    assert list(_parse_page(_soup("<html><body></body></html>"))) == []
