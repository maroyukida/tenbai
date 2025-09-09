# -*- coding: utf-8 -*-
"""
api-refetch CLI

RSS 発見時刻を基準に、発見後 1h/3h/6h/24h の各タイミングで
YouTube API (videos.list) を叩いてスナップショットを追加取得する。

要件:
- 対象時刻からの許容誤差: ±15分（デフォルト）
- QPS は 1.0〜2.0 程度の低め (デフォルト 1.5)
- 失敗時は指数バックオフでリトライ（チャンク単位）
- 必要なら ytapi_refetch_tasks テーブルを用意（簡易ログ用途）

実行例:
  python -m ytanalyzer.services.api_refetch --db data/rss_watch.sqlite --qps 1.5
"""
from __future__ import annotations

import argparse
import math
import os
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, Iterable, List, Optional, Tuple

import requests

from .api_fetcher import (
    open_db as open_api_db,
    fetch_videos,
    save_snapshots,
)


TARGET_OFFSETS = [1, 3, 6, 24]  # hours


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def iso_to_utc(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc).replace(microsecond=0)


def to_iso_z(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def ensure_tables(con: sqlite3.Connection) -> None:
    cur = con.cursor()
    # 簡易ログ用（任意）
    cur.execute(
        """
        create table if not exists ytapi_refetch_tasks(
          video_id text,
          target_offset_hours integer,
          target_time text,
          attempted_at text,
          status text,
          note text
        )
        """
    )
    con.commit()


def list_due_videos(
    con: sqlite3.Connection,
    now: datetime,
    tol_minutes: int,
    window_hours: int,
) -> List[str]:
    """発見から window_hours 以内の動画で、今まさに ±tol 分のウィンドウにある目標
    スナップショットが欠けているものを抽出して video_id を返す。
    """
    cur = con.cursor()
    start_iso = (now - timedelta(hours=window_hours)).isoformat()
    rows = cur.execute(
        "select video_id, discovered_at from rss_videos_discovered where discovered_at >= ?",
        (start_iso,),
    ).fetchall()
    due: List[str] = []
    for vid, disc_iso in rows:
        try:
            t0 = iso_to_utc(str(disc_iso))
        except Exception:
            continue
        for h in TARGET_OFFSETS:
            tgt = t0 + timedelta(hours=h)
            # 今がターゲット付近か？
            if abs((now - tgt).total_seconds()) > tol_minutes * 60:
                continue
            # 既に近傍スナップショットがあるか？
            lo = (tgt - timedelta(minutes=tol_minutes)).isoformat()
            hi = (tgt + timedelta(minutes=tol_minutes)).isoformat()
            hit = cur.execute(
                "select 1 from ytapi_snapshots where video_id=? and polled_at between ? and ? limit 1",
                (vid, lo, hi),
            ).fetchone()
            if hit:
                continue
            due.append(vid)
            break  # 1 本につき 1 回の再取得で十分
    return due


def chunks(lst: List[str], n: int) -> Iterable[List[str]]:
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


def run_once(
    db_path: str,
    api_key: str,
    qps: float = 1.5,
    tol_minutes: int = 15,
    window_hours: int = 30,
    max_ids: Optional[int] = None,
    batch_size: int = 50,
    max_daily_units: int = 9000,
) -> int:
    con = open_api_db(db_path)
    ensure_tables(con)
    now = utcnow()
    due = list_due_videos(con, now, tol_minutes=tol_minutes, window_hours=window_hours)
    if max_ids:
        due = due[:max_ids]
    # Quota guard: estimate today's used units from snapshots
    cur = con.cursor()
    used_snaps = cur.execute("select count(*) from ytapi_snapshots where date(polled_at)=date('now')").fetchone()[0]
    used_units = (used_snaps + 49) // 50
    remain_units = max(0, int(max_daily_units) - int(used_units))
    allow_ids = remain_units * 50
    if allow_ids <= 0:
        print(f"quota guard: used_units={used_units} >= max_daily_units={max_daily_units}; skip refetch")
        return 0
    if max_ids:
        allow_ids = min(allow_ids, max_ids)
    if allow_ids < len(due):
        due = due[:allow_ids]
        print(f"quota guard: limiting due to {len(due)} ids (remain_units={remain_units})")

    if not due:
        print("No due videos in window.")
        return 0

    sess = requests.Session()
    saved = 0
    backoff_base = 2.0
    for ids in chunks(due, max(1, min(batch_size, 50))):
        tries = 0
        while True:
            try:
                items = fetch_videos(api_key, ids, qps=qps, session=sess)
                saved += save_snapshots(con, items, {v: None for v in ids})
                # ログ
                cur = con.cursor()
                for vid in ids:
                    cur.execute(
                        "insert into ytapi_refetch_tasks(video_id, target_offset_hours, target_time, attempted_at, status, note) values(?,?,?,?,?,?)",
                        (
                            vid,
                            None,
                            None,
                            to_iso_z(now),
                            "ok",
                            None,
                        ),
                    )
                con.commit()
                break
            except requests.HTTPError as e:
                tries += 1
                wait = min(60.0, (backoff_base ** tries))
                print(f"HTTP error: {e}; retrying in {wait:.1f}s (try={tries})")
                time.sleep(wait)
                continue
            except requests.RequestException as e:
                tries += 1
                wait = min(60.0, (backoff_base ** tries))
                print(f"Request error: {e}; retrying in {wait:.1f}s (try={tries})")
                time.sleep(wait)
                continue
    print(f"refetched snapshots: {saved}")
    return saved


def build_arg_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Refetch YouTube video stats at 1h/3h/6h/24h after discovery")
    ap.add_argument("--db", default="data/rss_watch.sqlite", help="SQLite DB (rss_watch.sqlite)")
    ap.add_argument("--api-key", default=os.getenv("YOUTUBE_API_KEY"), help="YouTube API key (env YOUTUBE_API_KEY)")
    ap.add_argument("--qps", type=float, default=1.5, help="Requests per second upper bound")
    ap.add_argument("--tol-minutes", type=int, default=15, help="Tolerance minutes around target time")
    ap.add_argument("--window-hours", type=int, default=30, help="Discovery window hours to consider")
    ap.add_argument("--max-ids", type=int, default=0, help="Max number of videos to refetch in one run (0=all)")
    ap.add_argument("--batch-size", type=int, default=50, help="videos.list batch size (<=50)")
    ap.add_argument("--max-daily-units", type=int, default=9000, help="Quota guard: max units per day (estimate)")
    return ap


def main(argv: Optional[List[str]] = None) -> int:
    ap = build_arg_parser()
    args = ap.parse_args(argv)
    if not args.api_key:
        print("ERROR: --api-key 未指定か、環境変数 YOUTUBE_API_KEY が設定されていません")
        return 2
    return run_once(
        db_path=args.db,
        api_key=args.api_key,
        qps=args.qps,
        tol_minutes=args.tol_minutes,
        window_hours=args.window_hours,
        max_ids=(args.max_ids or None),
        batch_size=args.batch_size,
        max_daily_units=args.max_daily_units,
    )


if __name__ == "__main__":
    raise SystemExit(main())
