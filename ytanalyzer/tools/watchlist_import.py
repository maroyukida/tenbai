# -*- coding: utf-8 -*-
from __future__ import annotations

"""
Watchlist importer for youtube_channels_full.json (array of objects).

Features:
- Reads a JSON array with keys like: handle, title (and optionally channel_id or youtube_channel_url)
- Resolves @handle -> UCID by fetching the channel page if needed
- Inserts rows into rss_watchlist(channel_id, handle, title, added_at)
- Optionally seeds rss_channels to start RSS polling
- Emits NDJSON (data/watchlist_channels.ndjson) compatible with rss_watcher --channels-file

Usage:
  python -m ytanalyzer.tools.watchlist_import --json E:\hdd\youtube_channels_full.json
"""

import argparse
import json
import os
import re
import sqlite3
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Iterable, List, Optional, Tuple

import httpx

from ..services.rss_watcher import ensure_db as ensure_rss_db


UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36"
)
HEADERS = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ja,en;q=0.8",
}


def _utciso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def ensure_watchlist_table(con: sqlite3.Connection) -> None:
    con.execute(
        """
        create table if not exists rss_watchlist(
          channel_id text primary key,
          handle text,
          title text,
          added_at text
        )
        """
    )
    con.commit()


def normalize_handle(h: Optional[str]) -> Optional[str]:
    if not h or not isinstance(h, str):
        return None
    h = h.strip()
    if not h:
        return None
    if h.startswith("@"):  # typical @handle
        h = h[1:]
    return h


def extract_ucid_from_html(html: str) -> Optional[str]:
    # Try rel=canonical first
    m = re.search(r"href=\"https://www\.youtube\.com/channel/(UC[\w-]{20,})\"", html)
    if m:
        return m.group(1)
    # Fallback: "channelId":"UC..."
    m = re.search(r'"channelId"\s*:\s*"(UC[\w-]{20,})"', html)
    if m:
        return m.group(1)
    return None


def resolve_handle_to_ucid(client: httpx.Client, handle: str) -> Optional[str]:
    url = f"https://www.youtube.com/@{handle}"
    try:
        r = client.get(url, headers=HEADERS, timeout=20.0)
        if r.status_code >= 200 and r.status_code < 400 and r.text:
            ucid = extract_ucid_from_html(r.text)
            return ucid
        return None
    except httpx.HTTPError:
        return None


def row_to_ucid(client: httpx.Client, row: Dict[str, Any]) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Return (channel_id, handle, title)."""
    title = row.get("title") or row.get("channel_name") or None
    # Prefer explicit channel_id if present
    cid = row.get("channel_id")
    if isinstance(cid, str) and cid.startswith("UC"):
        return cid, normalize_handle(row.get("handle")), title
    # youtube_channel_url may exist in some datasets
    yurl = row.get("youtube_channel_url") or row.get("channel_url") or row.get("url")
    if isinstance(yurl, str):
        for part in yurl.split('/'):
            if part.startswith("UC"):
                return part, normalize_handle(row.get("handle")), title
    # Try handle
    h = normalize_handle(row.get("handle"))
    if h:
        uc = resolve_handle_to_ucid(client, h)
        if uc:
            return uc, h, title
    return None, normalize_handle(row.get("handle")), title


def import_watchlist(json_path: str, db_path: str, emit_ndjson: bool, seed_rss_channels: bool) -> Tuple[int, int]:
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
    con = ensure_rss_db(db_path)
    ensure_watchlist_table(con)

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("Input JSON must be an array of channel objects")

    added_watch = 0
    added_channels = 0
    ndjson_rows: List[str] = []

    with httpx.Client(http2=True, headers=HEADERS, timeout=20.0) as client:
        for row in data:
            if not isinstance(row, dict):
                continue
            cid, handle, title = row_to_ucid(client, row)
            if not cid:
                continue
            cur = con.cursor()
            cur.execute(
                "insert or ignore into rss_watchlist(channel_id, handle, title, added_at) values(?,?,?,?)",
                (cid, handle, title, _utciso()),
            )
            if cur.rowcount > 0:
                added_watch += 1

            if seed_rss_channels:
                # Seed into rss_channels for the watcher
                # Use a short jitter within 10 minutes
                jitter = timedelta(seconds=0)
                next_poll = (datetime.now(timezone.utc) + jitter).replace(microsecond=0).isoformat()
                cur.execute(
                    """
                    insert or ignore into rss_channels(
                      channel_id, etag, last_modified, last_checked_at, last_success_at, last_http_status,
                      failures, next_poll_at, poll_interval_sec, last_seen_published, last_seen_video_id, inflight, disabled
                    ) values(?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (cid, None, None, None, None, None, 0, next_poll, 3600, None, None, 0, 0),
                )
                if cur.rowcount > 0:
                    added_channels += 1

            if emit_ndjson:
                yurl = f"https://www.youtube.com/channel/{cid}"
                ndjson_rows.append(json.dumps({"youtube_channel_url": yurl}, ensure_ascii=False))

        con.commit()

    if emit_ndjson:
        out_dir = os.path.join("data")
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, "watchlist_channels.ndjson")
        tmp = out_path + ".tmp"
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            for line in ndjson_rows:
                f.write(line)
                f.write("\n")
        os.replace(tmp, out_path)
        print(f"Wrote NDJSON: {out_path} ({len(ndjson_rows)} lines)")

    return added_watch, added_channels


def build_arg_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Import youtube_channels_full.json into rss_watchlist")
    ap.add_argument("--json", required=True, help="Path to youtube_channels_full.json (array)")
    ap.add_argument("--db", default=os.path.join("data", "rss_watch.sqlite"))
    ap.add_argument("--no-ndjson", action="store_true", help="Do not emit data/watchlist_channels.ndjson")
    ap.add_argument("--no-seed", action="store_true", help="Do not insert into rss_channels")
    return ap


def main(argv: Optional[List[str]] = None) -> int:
    ap = build_arg_parser()
    args = ap.parse_args(argv)
    added_watch, added_channels = import_watchlist(args.json, args.db, not args.no_ndjson, not args.no_seed)
    print(f"watchlist added: {added_watch}, rss_channels added: {added_channels}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

