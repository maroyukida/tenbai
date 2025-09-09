# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import math
import sqlite3
from datetime import datetime, timezone, timedelta
from typing import Optional


def parse_date(s: Optional[str]) -> str:
    if not s:
        jst = timezone(timedelta(hours=9))
        d = datetime.now(jst).date() - timedelta(days=1)
        return d.strftime('%Y-%m-%d')
    s = s.strip()
    if len(s) == 8 and s.isdigit():
        return f"{s[0:4]}-{s[4:6]}-{s[6:8]}"
    return s


def ensure_tables(con: sqlite3.Connection) -> None:
    cur = con.cursor()
    cur.execute(
        """
        create table if not exists ytapi_channel_snapshots(
          id integer primary key autoincrement,
          channel_id text, title text, polled_at text,
          view_count integer, subscriber_count integer, video_count integer
        )
        """
    )
    cur.execute(
        """
        create table if not exists channel_week_ranks(
          end_date text,
          channel_id text,
          title text,
          delta_views integer,
          delta_subs integer,
          score real,
          updated_at text,
          primary key(end_date, channel_id)
        )
        """
    )
    con.commit()


def nearest_after(cur: sqlite3.Cursor, cid: str, iso: str):
    r = cur.execute("select view_count, subscriber_count, polled_at from ytapi_channel_snapshots where channel_id=? and polled_at>=? order by polled_at asc limit 1", (cid, iso)).fetchone()
    if not r:
        return None
    return int(r[0] or 0), int(r[1] or 0), str(r[2])


def nearest_before(cur: sqlite3.Cursor, cid: str, iso: str):
    r = cur.execute("select view_count, subscriber_count, polled_at from ytapi_channel_snapshots where channel_id=? and polled_at<=? order by polled_at desc limit 1", (cid, iso)).fetchone()
    if not r:
        return None
    return int(r[0] or 0), int(r[1] or 0), str(r[2])


def run_once(db: str, end_date: Optional[str]) -> int:
    end_ = parse_date(end_date)
    start_dt = datetime.fromisoformat(end_ + 'T00:00:00+00:00') - timedelta(days=6)
    start_iso = start_dt.isoformat()
    end_iso = f"{end_}T23:59:59+00:00"
    con = sqlite3.connect(db, timeout=60); con.row_factory = sqlite3.Row
    ensure_tables(con)
    cur = con.cursor()
    ids = [r[0] for r in cur.execute("select distinct channel_id from ytapi_channel_snapshots where polled_at<=?", (end_iso,)).fetchall()]
    now_iso = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    saved = 0
    for cid in ids:
        a = nearest_after(cur, cid, start_iso); b = nearest_before(cur, cid, end_iso)
        if not a or not b: continue
        v0, s0, t0 = a; v1, s1, t1 = b
        if t1 < t0: continue
        dv = max(0, v1 - v0); ds = max(0, s1 - s0)
        score = math.log1p(dv) + 0.25 * math.log1p(ds)
        title = cur.execute("select title from ytapi_channel_snapshots where channel_id=? order by polled_at desc limit 1", (cid,)).fetchone()
        title = title[0] if title else None
        cur.execute(
            """
            insert into channel_week_ranks(end_date, channel_id, title, delta_views, delta_subs, score, updated_at)
            values(?,?,?,?,?,?,?)
            on conflict(end_date, channel_id) do update set
              title=excluded.title,
              delta_views=excluded.delta_views,
              delta_subs=excluded.delta_subs,
              score=excluded.score,
              updated_at=excluded.updated_at
            """,
            (end_, cid, title, dv, ds, score, now_iso),
        )
        saved += 1
    con.commit()
    print(f"week ranks saved: {saved} for week ending {end_}")
    return saved


def build_arg_parser():
    ap = argparse.ArgumentParser(description="Compute weekly channel ranks from channel snapshots")
    ap.add_argument("--db", default="data/rss_watch.sqlite")
    ap.add_argument("--end-date", default=None, help="YYYY-MM-DD or YYYYMMDD; default=yesterday (JST)")
    return ap


def main(argv: Optional[list] = None) -> int:
    ap = build_arg_parser(); args = ap.parse_args(argv)
    return run_once(args.db, args.end_date)


if __name__ == "__main__":
    raise SystemExit(main())

