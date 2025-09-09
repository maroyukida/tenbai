# -*- coding: utf-8 -*-
from __future__ import annotations

"""
Populate trending_ranks by a fallback "popular" score using single snapshots.

Why: When only one ytapi_snapshot exists per video, the growth ranker skips it.
This tool computes a naive popularity score based on current views normalized by
age since published, so the UI can show more items even with sparse snapshots.

Usage:
  python -m ytanalyzer.tools.popular_ranker --db data/rss_watch.sqlite \
      --window-hours 168 --limit 50000 --alpha 0.3
"""

import argparse
import math
import json
import re
import sqlite3
from datetime import datetime, timezone
from typing import Optional

from ..services.growth_ranker import CATEGORY_MAP  # reuse static map


def _is_short_like(duration_seconds: Optional[int], title: Optional[str], keywords_json: Optional[str], canonical_url: Optional[str] = None) -> bool:
    """Safer Shorts detection (<=75s definite, 76..180s needs hints)."""
    text = (title or "").lower()
    tags = []
    try:
        if keywords_json:
            arr = json.loads(keywords_json)
            if isinstance(arr, list):
                tags = [str(x).lower() for x in arr if x]
    except Exception:
        pass
    blob = (text + " " + " ".join(tags) + " " + (canonical_url or "")).lower()
    rx = r"(?i)(#?shorts?\b|vertical\b|reels?\b|tiktok\b|short\b|ショート|縦動画|縦型)"
    def hinted() -> bool:
        return (re.search(rx, blob) is not None) or ("/shorts/" in blob)
    try:
        if duration_seconds is not None:
            d = int(duration_seconds)
            if d <= 60:
                return True
            if d <= 180:
                return hinted()
            return False
    except Exception:
        pass
    return hinted()


def parse_iso(ts: Optional[str]) -> Optional[datetime]:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(str(ts).replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return None


def open_db(path: str) -> sqlite3.Connection:
    con = sqlite3.connect(path, timeout=60)
    con.row_factory = sqlite3.Row
    return con


def upsert(con: sqlite3.Connection, row: sqlite3.Row, score: float) -> None:
    cur = con.cursor()
    cur.execute(
        """
        insert into trending_ranks(
          video_id, channel_id, channel_title, title, thumb_hq, published_at,
          category_id, category_name, is_short, score, d1h, d3h, d6h,
          v0, v1, v3, v6, current_views, likes_per_hour, updated_at
        ) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?, datetime('now'))
        on conflict(video_id) do update set
          channel_id=excluded.channel_id,
          channel_title=excluded.channel_title,
          title=excluded.title,
          thumb_hq=excluded.thumb_hq,
          published_at=excluded.published_at,
          category_id=excluded.category_id,
          category_name=excluded.category_name,
          is_short=excluded.is_short,
          score=excluded.score,
          d1h=excluded.d1h,
          d3h=excluded.d3h,
          d6h=excluded.d6h,
          v0=excluded.v0,
          v1=excluded.v1,
          v3=excluded.v3,
          v6=excluded.v6,
          current_views=excluded.current_views,
          likes_per_hour=excluded.likes_per_hour,
          updated_at=datetime('now')
        """,
        (
            row["video_id"], row["channel_id"], row["channel_title"], row["title"], row["thumb_hq"], row["published_at"],
            row["category_id"], row["category_name"], row["is_short"], score,
            None, None, None,
            None, None, None, None,
            row["view_count"], None,
        ),
    )
    con.commit()


def run_once(db: str, window_hours: int, limit: int, alpha: float) -> int:
    con = open_db(db)
    cur = con.cursor()
    # latest snapshot per video within window (published window)
    rows = cur.execute(
        """
        with last as (
          select video_id, max(polled_at) as maxp from ytapi_snapshots group by video_id
        )
        select s.video_id, s.view_count, s.like_count, s.duration_seconds, s.category_id, s.channel_title, s.polled_at,
               v.channel_id, v.title, v.published_at, v.thumb_hq, v.keywords_json, v.canonical_url
        from ytapi_snapshots s
        join last on last.video_id=s.video_id and last.maxp=s.polled_at
        join rss_videos v on v.video_id=s.video_id
        where strftime('%s', replace(substr(coalesce(v.published_at,''),1,19),'T',' ')) >= strftime('%s','now', ?)
        order by s.view_count desc
        limit ?
        """,
        (f"-{int(window_hours)} hours", int(limit)),
    ).fetchall()

    now = datetime.now(timezone.utc)
    done = 0
    for r in rows:
        pub = parse_iso(r["published_at"]) or parse_iso(r["polled_at"]) or now
        polled = parse_iso(r["polled_at"]) or now
        age_h = max(0.5, (polled - pub).total_seconds() / 3600.0)
        views = max(0.0, float(r["view_count"] or 0))
        # popularity score: log(views) normalized by age^alpha
        score = math.log1p(views) / max(1e-6, math.pow(age_h, max(0.0, alpha)))
        is_short = 1 if _is_short_like(r["duration_seconds"], r["title"], r["keywords_json"], r.get("canonical_url")) else 0
        cat_name = CATEGORY_MAP.get(str(r["category_id"]) if r["category_id"] is not None else "", "Unknown")
        row = {
            "video_id": r["video_id"],
            "channel_id": r["channel_id"],
            "channel_title": r["channel_title"],
            "title": r["title"],
            "thumb_hq": r["thumb_hq"],
            "published_at": r["published_at"],
            "category_id": r["category_id"],
            "category_name": cat_name,
            "is_short": is_short,
            "view_count": int(r["view_count"] or 0),
        }
        upsert(con, row, float(score))
        done += 1
    return done


def build_arg_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Populate trending_ranks using single-snapshot popularity score")
    ap.add_argument("--db", default="data/rss_watch.sqlite")
    ap.add_argument("--window-hours", type=int, default=168)
    ap.add_argument("--limit", type=int, default=50000)
    ap.add_argument("--alpha", type=float, default=0.3, help="age normalization exponent")
    return ap


def main(argv: Optional[list[str]] = None) -> int:
    ap = build_arg_parser()
    args = ap.parse_args(argv)
    n = run_once(args.db, args.window_hours, args.limit, args.alpha)
    print(f"popular upserted: {n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
