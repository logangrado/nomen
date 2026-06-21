import io
from pathlib import Path
from typing import Iterable

import httpx
import psycopg


def download_zip(url: str, dest: Path, force: bool = False) -> Path:
    """Download a zip file to dest. Skips if dest exists and force is False."""
    if dest.exists() and not force:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {url} -> {dest}")
    headers = {"User-Agent": "Mozilla/5.0 (compatible; nomen-pipeline/1.0)"}
    with httpx.stream("GET", url, follow_redirects=True, headers=headers) as resp:
        resp.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in resp.iter_bytes(chunk_size=65536):
                f.write(chunk)
    return dest


def normalize_name(name: str) -> str:
    """Return name in canonical lowercase form for storage."""
    return name.strip().lower()


def copy_records(
    conn: psycopg.Connection,
    table: str,
    columns: list[str],
    rows: Iterable[tuple],
    log_every: int = 0,
) -> int:
    """Bulk-load rows into table via psycopg COPY FROM STDIN. Returns row count."""
    count = 0
    col_list = ", ".join(columns)
    with conn.cursor() as cur:
        with cur.copy(f"COPY {table} ({col_list}) FROM STDIN") as copy:
            for row in rows:
                copy.write_row(row)
                count += 1
                if log_every and count % log_every == 0:
                    print(f"  {count:,} rows copied...", flush=True)
    return count
