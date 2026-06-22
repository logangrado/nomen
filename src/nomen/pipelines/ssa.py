"""SSA (US Social Security Administration) baby name data pipeline.

Sources:
  National: https://www.ssa.gov/oact/babynames/names.zip
            Contains yob{YEAR}.txt files: Name,Gender,Count
  State:    https://www.ssa.gov/oact/babynames/state/namesbystate.zip
            Contains {STATE}.TXT files: State,Gender,Year,Name,Count
"""
import io
import os
import re
from pathlib import Path
from zipfile import ZipFile

_VALID_NAME = re.compile(r"^[a-z][a-z'\-]*$")

import psycopg

from nomen.pipelines.base import copy_records, download_zip, normalize_name

NATIONAL_URL = "https://www.ssa.gov/oact/babynames/names.zip"
STATE_URL = "https://www.ssa.gov/oact/babynames/state/namesbystate.zip"

DATA_DIR = Path("data/ssa")

# Mapping from USPS 2-letter abbreviations to ISO 3166-2 region codes
USPS_TO_ISO: dict[str, str] = {
    "AL": "US-AL", "AK": "US-AK", "AZ": "US-AZ", "AR": "US-AR",
    "CA": "US-CA", "CO": "US-CO", "CT": "US-CT", "DE": "US-DE",
    "DC": "US-DC", "FL": "US-FL", "GA": "US-GA", "HI": "US-HI",
    "ID": "US-ID", "IL": "US-IL", "IN": "US-IN", "IA": "US-IA",
    "KS": "US-KS", "KY": "US-KY", "LA": "US-LA", "ME": "US-ME",
    "MD": "US-MD", "MA": "US-MA", "MI": "US-MI", "MN": "US-MN",
    "MS": "US-MS", "MO": "US-MO", "MT": "US-MT", "NE": "US-NE",
    "NV": "US-NV", "NH": "US-NH", "NJ": "US-NJ", "NM": "US-NM",
    "NY": "US-NY", "NC": "US-NC", "ND": "US-ND", "OH": "US-OH",
    "OK": "US-OK", "OR": "US-OR", "PA": "US-PA", "RI": "US-RI",
    "SC": "US-SC", "SD": "US-SD", "TN": "US-TN", "TX": "US-TX",
    "UT": "US-UT", "VT": "US-VT", "VA": "US-VA", "WA": "US-WA",
    "WV": "US-WV", "WI": "US-WI", "WY": "US-WY",
}

STATE_NAMES: dict[str, str] = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
    "DC": "District of Columbia", "FL": "Florida", "GA": "Georgia", "HI": "Hawaii",
    "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa",
    "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine",
    "MD": "Maryland", "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota",
    "MS": "Mississippi", "MO": "Missouri", "MT": "Montana", "NE": "Nebraska",
    "NV": "Nevada", "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico",
    "NY": "New York", "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio",
    "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island",
    "SC": "South Carolina", "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas",
    "UT": "Utah", "VT": "Vermont", "VA": "Virginia", "WA": "Washington",
    "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming",
}


def parse_national(zip_path: Path, verbose: bool = False):
    """Yield name_stats row dicts from the SSA national zip.

    Format: yob{YEAR}.txt lines are  Name,Gender,Count
    """
    with ZipFile(zip_path) as zf:
        files = sorted(f for f in zf.namelist() if f.startswith("yob") and f.endswith(".txt"))
        for i, fname in enumerate(files, 1):
            year = int(fname[3:7])
            if verbose:
                print(f"  national {year} ({i}/{len(files)})", flush=True)
            with zf.open(fname) as f:
                for line in io.TextIOWrapper(f, encoding="utf-8"):
                    line = line.strip()
                    if not line:
                        continue
                    name, gender, count = line.split(",")
                    name = normalize_name(name)
                    if not _VALID_NAME.match(name):
                        continue
                    yield {
                        "name": name,
                        "source": "SSA",
                        "year": year,
                        "month": None,
                        "region_code": "US",
                        "gender": gender,
                        "count": int(count),
                        "rank": None,
                    }


def parse_states(zip_path: Path, verbose: bool = False):
    """Yield name_stats row dicts from the SSA state zip.

    Format: {STATE}.TXT lines are  State,Gender,Year,Name,Count
    """
    with ZipFile(zip_path) as zf:
        files = sorted(
            f for f in zf.namelist()
            if f.upper().endswith(".TXT") and "readme" not in f.lower()
        )
        for i, fname in enumerate(files, 1):
            if verbose:
                print(f"  state {fname} ({i}/{len(files)})", flush=True)
            with zf.open(fname) as f:
                for line in io.TextIOWrapper(f, encoding="utf-8"):
                    line = line.strip()
                    if not line:
                        continue
                    state, gender, year, name, count = line.split(",")
                    state = state.strip()
                    if state not in USPS_TO_ISO:
                        continue
                    name = normalize_name(name)
                    if not _VALID_NAME.match(name):
                        continue
                    yield {
                        "name": name,
                        "source": "SSA",
                        "year": int(year),
                        "month": None,
                        "region_code": USPS_TO_ISO[state],
                        "gender": gender.strip(),
                        "count": int(count),
                        "rank": None,
                    }


def _seed_regions(conn: psycopg.Connection) -> None:
    """Insert US country record and all state records (idempotent)."""
    conn.execute(
        """
        INSERT INTO regions (code, name, country_iso2, region_type)
        VALUES ('US', 'United States', 'US', 'country')
        ON CONFLICT (code) DO NOTHING
        """
    )
    rows = [
        (USPS_TO_ISO[usps], STATE_NAMES[usps], "US", "state")
        for usps in USPS_TO_ISO
    ]
    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO regions (code, name, country_iso2, region_type)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (code) DO NOTHING
            """,
            rows,
        )


def _upsert_names(conn: psycopg.Connection, names: set[str]) -> None:
    """Insert unique name strings; skip existing ones."""
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO names (name) VALUES (%s) ON CONFLICT (name) DO NOTHING",
            [(n,) for n in names],
        )


def _collect_unique_names(zip_path: Path, parser) -> set[str]:
    """Stream a zip through parser, returning only the unique name strings."""
    return {row["name"] for row in parser(zip_path)}


def load_ssa(force_download: bool = False) -> None:
    """Download SSA zips and bulk-load into name_stats table.

    Uses two passes to stay memory-efficient:
      Pass 1 — collect unique name strings from both zips (small set, ~100K)
      Pass 2 — seed DB, then COPY name_stats rows from both zips
    """
    national_zip = download_zip(NATIONAL_URL, DATA_DIR / "names.zip", force_download)
    state_zip = download_zip(STATE_URL, DATA_DIR / "namesbystate.zip", force_download)

    # Pass 1: collect all unique names (need both to deduplicate across sources)
    print("Pass 1: collecting unique names (national)...")
    unique_names = {row["name"] for row in parse_national(national_zip, verbose=True)}
    print("Pass 1: collecting unique names (states)...")
    unique_names |= {row["name"] for row in parse_states(state_zip, verbose=True)}
    print(f"  {len(unique_names):,} unique names found")

    db_url = os.environ["DATABASE_URL"]
    with psycopg.connect(db_url) as conn:
        print("Seeding regions...")
        _seed_regions(conn)
        conn.commit()

        print(f"Upserting {len(unique_names):,} names...")
        _upsert_names(conn, unique_names)
        conn.commit()

        # Clear existing SSA rows so re-runs don't accumulate duplicates
        print("Truncating name_stats (SSA rows)...")
        conn.execute("DELETE FROM name_stats WHERE source = 'SSA'")
        conn.commit()

        # Pass 2: COPY all stat rows
        columns = ["name", "source", "year", "month", "region_code", "gender", "count", "rank"]

        def all_rows():
            for row in parse_national(national_zip, verbose=True):
                yield (
                    row["name"], row["source"], row["year"], row["month"],
                    row["region_code"], row["gender"], row["count"], row["rank"],
                )
            for row in parse_states(state_zip, verbose=True):
                yield (
                    row["name"], row["source"], row["year"], row["month"],
                    row["region_code"], row["gender"], row["count"], row["rank"],
                )

        print("Pass 2: loading name_stats via COPY...")
        count = copy_records(conn, "name_stats", columns, all_rows(), log_every=500_000)
        conn.commit()

    print(f"Done. Loaded {count:,} rows into name_stats.")
