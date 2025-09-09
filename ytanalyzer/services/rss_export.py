# -*- coding: utf-8 -*-
"""
NDJSON エクスポート（直近ウィンドウの新着動画をファイル出力）

仕様:
- 集計対象: discovered_at ∈ [end - window_minutes, end)
- 出力先: exports/rss_discovered_YYYYMMDDTHHMM.jsonl （UTC）
- 各行: {video_id, channel_id, title, discovered_at(ISO8601Z), published_at(ISO8601Z)}
- 並び: discovered_at 昇順、同一ファイル内の重複 video_id は除外
- 空ならファイル未作成で正常終了
- 原子性: .tmp に書いてからリネーム
- 初回大量取得のノイズ回避用: --min-published-hours で古い published を除外（既定=48h）

実行例:
  # 単発
  python -m ytanalyzer.cli rss-export --db data/rss_watch.sqlite --out-dir exports --window-minutes 10

  # ループ（10分毎正時アライン）
  python -m ytanalyzer.cli rss-export --db data/rss_watch.sqlite --out-dir exports --window-minutes 10 --loop
"""
from __future__ import annotations

import argparse
import os
import sqlite3
from typing import Iterable, List, Optional, Tuple, Dict, Any
from datetime import datetime, timezone, timedelta
import time
import json
from email.utils import parsedate_to_datetime


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def floor_to_minute(dt: datetime) -> datetime:
    return dt.replace(second=0, microsecond=0)


def ceil_to_window(dt: datetime, minutes: int) -> datetime:
    dt = dt.replace(second=0, microsecond=0)
    rem = dt.minute % minutes
    if rem == 0:
        return dt
    add = minutes - rem
    return dt + timedelta(minutes=add)


def to_iso_z(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_any_dt(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        # handle ISO with Z or offset
        s2 = s.replace("Z", "+00:00")
        return datetime.fromisoformat(s2).astimezone(timezone.utc)
    except Exception:
        pass
    try:
        dt = parsedate_to_datetime(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def ensure_dir(p: str) -> None:
    os.makedirs(p, exist_ok=True)


def file_stamp(dt: datetime) -> str:
    # UTC 名で YYYYMMDDTHHMM
    return dt.strftime("%Y%m%dT%H%M")


def open_db(path: str) -> sqlite3.Connection:
    con = sqlite3.connect(path, timeout=60)
    con.row_factory = sqlite3.Row
    return con


def select_window(con: sqlite3.Connection, start_iso: str, end_iso: str) -> List[Dict[str, Any]]:
    # 期間内の discovered を昇順で取得。published は動画テーブルから参照
    sql = (
        "SELECT d.video_id, d.channel_id, d.title as d_title, d.discovered_at, v.published_at as v_published, v.title as v_title "
        "FROM rss_videos_discovered d LEFT JOIN rss_videos v ON v.video_id=d.video_id "
        "WHERE d.discovered_at >= ? AND d.discovered_at < ? "
        "ORDER BY d.discovered_at ASC"
    )
    rows = [dict(r) for r in con.execute(sql, (start_iso, end_iso)).fetchall()]
    return rows


def export_once(db_path: str, out_dir: str, window_minutes: int, end_time: Optional[datetime], min_published_hours: int) -> int:
    end_dt = floor_to_minute(end_time or utcnow())
    start_dt = end_dt - timedelta(minutes=window_minutes)
    start_iso = start_dt.isoformat()
    end_iso = end_dt.isoformat()

    con = open_db(db_path)
    rows = select_window(con, start_iso, end_iso)

    # 去る初期巡回ノイズ: 古い published は除外（既定48h）
    pub_threshold = end_dt - timedelta(hours=max(0, min_published_hours))

    seen = set()
    items: List[Dict[str, Any]] = []
    for r in rows:
        vid = r.get("video_id")
        if not vid or vid in seen:
            continue
        seen.add(vid)
        title = r.get("v_title") or r.get("d_title") or ""
        disc_dt = parse_any_dt(r.get("discovered_at"))
        pub_dt = parse_any_dt(r.get("v_published"))
        # 古い published はスキップ（pub_dt が取れない場合は採用）
        if pub_dt is not None and pub_dt < pub_threshold:
            continue
        items.append({
            "video_id": vid,
            "channel_id": r.get("channel_id"),
            "title": title,
            "discovered_at": to_iso_z(disc_dt) if disc_dt else to_iso_z(end_dt),
            "published_at": to_iso_z(pub_dt) if pub_dt else None,
        })

    if not items:
        # 0 件ならファイルを作成しない
        print(f"No items in window [{to_iso_z(start_dt)} - {to_iso_z(end_dt)}), skip file")
        return 0

    ensure_dir(out_dir)
    stamp = file_stamp(end_dt)
    out_path = os.path.join(out_dir, f"rss_discovered_{stamp}.jsonl")
    tmp_path = out_path + ".tmp"

    with open(tmp_path, "w", encoding="utf-8", newline="\n") as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False, separators=(",", ":")))
            f.write("\n")
    os.replace(tmp_path, out_path)
    print(f"Wrote {len(items)} items -> {out_path}")
    return 0


def loop_export(db_path: str, out_dir: str, window_minutes: int, min_published_hours: int) -> int:
    # 正時アラインで 10 分ごとに実行
    while True:
        now = utcnow()
        next_cut = ceil_to_window(now, window_minutes)
        # 次のカットで [cut-window, cut) を出力
        sleep_sec = (next_cut - now).total_seconds()
        if sleep_sec > 0:
            time.sleep(sleep_sec)
        try:
            export_once(db_path, out_dir, window_minutes, next_cut, min_published_hours)
        except Exception as e:
            # ログだけ出して続行
            print(f"export error: {e}")


def build_arg_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="NDJSON exporter for RSS discovered videos")
    ap.add_argument("--db", required=True, help="SQLite DB (rss_watch.sqlite)")
    ap.add_argument("--out-dir", default="exports", help="出力先ディレクトリ")
    ap.add_argument("--window-minutes", type=int, default=10, help="集計ウィンドウ（分）")
    ap.add_argument("--now", type=str, default=None, help="単発実行のエンド時刻（UTC ISO、Z可）。未指定は現在時刻")
    ap.add_argument("--loop", action="store_true", help="10分ごとに繰り返し出力")
    ap.add_argument("--min-published-hours", type=int, default=48, help="この時間より古い published は除外（初回巡回対策）")
    return ap


def main(argv: Optional[List[str]] = None) -> int:
    ap = build_arg_parser()
    args = ap.parse_args(argv)
    if args.loop:
        return loop_export(args.db, args.out_dir, args.window_minutes, args.min_published_hours) or 0
    end_dt = parse_any_dt(args.now) if args.now else None
    return export_once(args.db, args.out_dir, args.window_minutes, end_dt, args.min_published_hours) or 0


if __name__ == "__main__":
    raise SystemExit(main())

