import io
import zipfile
from pathlib import Path

import pytest

from nomen.pipelines.ssa import USPS_TO_ISO, parse_national, parse_states


def _make_zip(entries: dict[str, str], dest: Path) -> Path:
    """Write a zip file with string contents to dest and return dest."""
    with zipfile.ZipFile(dest, "w") as zf:
        for fname, content in entries.items():
            zf.writestr(fname, content)
    return dest


# ---------------------------------------------------------------------------
# parse_national
# ---------------------------------------------------------------------------

def test_parse_national_basic(tmp_path):
    content = "Emma,F,20000\nLiam,M,19500\n"
    zip_path = _make_zip({"yob2020.txt": content}, tmp_path / "names.zip")

    rows = list(parse_national(zip_path))
    assert len(rows) == 2

    emma = next(r for r in rows if r["name"] == "emma")
    assert emma["year"] == 2020
    assert emma["gender"] == "F"
    assert emma["count"] == 20000
    assert emma["region_code"] == "US"
    assert emma["source"] == "SSA"
    assert emma["month"] is None
    assert emma["rank"] is None


def test_parse_national_lowercases_name(tmp_path):
    content = "MacKenzie,F,500\n"
    zip_path = _make_zip({"yob2010.txt": content}, tmp_path / "names.zip")
    rows = list(parse_national(zip_path))
    assert rows[0]["name"] == "mackenzie"


def test_parse_national_skips_non_yob_files(tmp_path):
    """NationalReadMe.pdf and similar files should be ignored."""
    zip_path = _make_zip(
        {
            "yob2020.txt": "Emma,F,1000\n",
            "NationalReadMe.pdf": "not csv data",
        },
        tmp_path / "names.zip",
    )
    rows = list(parse_national(zip_path))
    assert len(rows) == 1


def test_parse_national_multiple_years(tmp_path):
    zip_path = _make_zip(
        {
            "yob1990.txt": "Alice,F,5000\n",
            "yob2000.txt": "Alice,F,6000\n",
        },
        tmp_path / "names.zip",
    )
    rows = list(parse_national(zip_path))
    years = {r["year"] for r in rows}
    assert years == {1990, 2000}


# ---------------------------------------------------------------------------
# parse_states
# ---------------------------------------------------------------------------

def test_parse_states_basic(tmp_path):
    content = "CA,F,2020,Olivia,5000\n"
    zip_path = _make_zip({"CA.TXT": content}, tmp_path / "states.zip")

    rows = list(parse_states(zip_path))
    assert len(rows) == 1
    assert rows[0]["region_code"] == "US-CA"
    assert rows[0]["name"] == "olivia"
    assert rows[0]["year"] == 2020
    assert rows[0]["gender"] == "F"
    assert rows[0]["count"] == 5000
    assert rows[0]["source"] == "SSA"


def test_parse_states_iso_code_mapping(tmp_path):
    """All state codes in the file should map to US-{STATE} format."""
    lines = "\n".join(f"{usps},F,2020,Test,100" for usps in USPS_TO_ISO)
    zip_path = _make_zip({"ALL.TXT": lines}, tmp_path / "states.zip")
    rows = list(parse_states(zip_path))
    returned_codes = {r["region_code"] for r in rows}
    assert returned_codes == set(USPS_TO_ISO.values())


def test_parse_states_lowercases_name(tmp_path):
    content = "TX,M,2015,JAMES,3000\n"
    zip_path = _make_zip({"TX.TXT": content}, tmp_path / "states.zip")
    rows = list(parse_states(zip_path))
    assert rows[0]["name"] == "james"
