# -*- coding: utf-8 -*-
from __future__ import annotations

"""
YouTube channels.list fetcher

rss_watch.sqlite の rss_channels から channel_id を取得し、
YouTube Data API v3 channels.list で統計をスナップショット保存する。

テーブル: ytapi_channel_snapshots
  channel_id TEXT, title TEXT, polled_at TEXT,
  view_count INTEGER, subscriber_count INTEGER, video_count INTEGER

使い方:
  python -m ytanalyzer.services.channel_fetcher --db data/rss_watch.sqlite --api-key $YOUTUBE_API_KEY \
      --qps 1.0 --batch-size 50 --max-channels 50000
"""

import argparse
import os
import sqlite3
import time
from typing import Iterable, List, Optional, Dict

import requests
from datetime import datetime, timezone


API_URL = "https://www.googleapis.com/youtube/v3/channels"


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def open_db(path: str) -> sqlite3.Connection:
    con = sqlite3.connect(path, timeout=60)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    cur.execute(
        """
        create table if not exists ytapi_channel_snapshots(
          id integer primary key autoincrement,
          channel_id text,
          title text,
          polled_at text,
          view_count integer,
          subscriber_count integer,
          video_count integer
        )
        """
    )
    con.commit()
    return con


def list_channels(con: sqlite3.Connection, max_channels: Optional[int] = None) -> List[str]:
    sql = "select channel_id from rss_channels where channel_id is not null and channel_id!='' order by channel_id"
    rows = con.execute(sql).fetchall()
    ids = [r[0] for r in rows]
    if max_channels:
        ids = ids[:max_channels]
    return ids


def chunks(lst: List[str], n: int) -> Iterable[List[str]]:
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


def fetch_channels(api_key: str, ids: List[str], session: Optional[requests.Session] = None, qps: float = 1.0) -> List[Dict]:
    if not ids:
        return []
    sess = session or requests.Session()
    params = {
        "part": "statistics,snippet",
        "id": ",".join(ids),
        "key": api_key,
        "maxResults": 50,
    }
    time.sleep(max(0.0, 1.0 / max(qps, 0.1)))
    r = sess.get(API_URL, params=params, timeout=30)
    r.raise_for_status()
    return r.json().get("items", [])


def save_snapshots(con: sqlite3.Connection, items: List[Dict]) -> int:
    cur = con.cursor()
    now = utcnow_iso()
    n = 0
    for it in items:
        cid = it.get("id")
        if not cid:
            continue
        snip = it.get("snippet", {})
        stats = it.get("statistics", {})
        title = snip.get("title")
        vc = int(stats.get("viewCount", 0) or 0)
        sc = int(stats.get("subscriberCount", 0) or 0)
        vcnt = int(stats.get("videoCount", 0) or 0)
        cur.execute(
            """
            insert into ytapi_channel_snapshots(channel_id, title, polled_at, view_count, subscriber_count, video_count)
            values(?,?,?,?,?,?)
            """,
            (cid, title, now, vc, sc, vcnt),
        )
        n += 1
    con.commit()
    return n


def run_once(db: str, api_key: str, qps: float, batch_size: int, max_channels: Optional[int]) -> int:
    con = open_db(db)
    ids = list_channels(con, max_channels)
    if not ids:
        print("No channels in rss_channels.")
        return 0
    sess = requests.Session()
    saved = 0
    for group in chunks(ids, max(1, min(batch_size, 50))):
        try:
            items = fetch_channels(api_key, group, session=sess, qps=qps)
        except requests.HTTPError as e:
            print(f"HTTP error: {e}; ids={group[:2]}...")
            time.sleep(5)
            continue
        except requests.RequestException as e:
            print(f"Request error: {e}")
            time.sleep(5)
            continue
        saved += save_snapshots(con, items)
    print(f"channel snapshots saved: {saved}")
    return saved


def build_arg_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Fetch channel statistics snapshots")
    ap.add_argument("--db", default="data/rss_watch.sqlite")
    ap.add_argument("--api-key", default=os.getenv("YOUTUBE_API_KEY"))
    ap.add_argument("--qps", type=float, default=1.0)
    ap.add_argument("--batch-size", type=int, default=50)
    ap.add_argument("--max-channels", type=int, default=0)
    return ap


def main(argv: Optional[List[str]] = None) -> int:
    ap = build_arg_parser()
    args = ap.parse_args(argv)
    if not args.api_key:
        print("ERROR: --api-key not set (or env YOUTUBE_API_KEY)")
        return 2
    return run_once(args.db, args.api_key, args.qps, args.batch_size, (args.max_channels or None))


if __name__ == "__main__":
    raise SystemExit(main())

