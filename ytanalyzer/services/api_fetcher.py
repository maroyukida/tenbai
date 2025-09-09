# -*- coding: utf-8 -*-
"""
YouTube Data API v3 フェッチャ（Step②）

入力: exports/rss_discovered_*.jsonl（NDJSON; 1行=1動画）
処理: video_id を最大 50 件ずつ videos.list に投入し、スナップショット保存
保存: data/rss_watch.sqlite のテーブル ytapi_snapshots / api_imported_files

注意:
- APIキー: 環境変数 YOUTUBE_API_KEY または CLI --api-key で指定
- QPS 制御: --qps で 1〜2 などから安全運用
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from glob import glob
from typing import Dict, Iterable, List, Optional, Tuple

import requests


API_URL = "https://www.googleapis.com/youtube/v3/videos"


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def ensure_tables(con: sqlite3.Connection) -> None:
    cur = con.cursor()
    cur.execute(
        """
        create table if not exists api_imported_files(
          file_name text primary key,
          mtime_utc text,
          imported_at text
        )
        """
    )
    cur.execute(
        """
        create table if not exists ytapi_snapshots(
          id integer primary key autoincrement,
          video_id text,
          channel_id text,
          channel_title text,
          polled_at text,
          view_count integer,
          like_count integer,
          comment_count integer,
          duration_seconds integer,
          category_id text,
          live_broadcast_content text
        )
        """
    )
    # add missing column channel_title if needed
    cols = {r[1] for r in cur.execute("pragma table_info(ytapi_snapshots)").fetchall()}
    if "channel_title" not in cols:
        cur.execute("alter table ytapi_snapshots add column channel_title text")
    con.commit()


def open_db(path: str) -> sqlite3.Connection:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    con = sqlite3.connect(path, timeout=60)
    con.row_factory = sqlite3.Row
    ensure_tables(con)
    return con


def list_unprocessed(in_dir: str, con: sqlite3.Connection, pattern: str = "rss_discovered_*.jsonl") -> List[str]:
    files = sorted(glob(os.path.join(in_dir, pattern)))
    if not files:
        return []
    cur = con.cursor()
    processed = {r[0] for r in cur.execute("select file_name from api_imported_files").fetchall()}
    return [f for f in files if os.path.basename(f) not in processed]


def mark_processed(con: sqlite3.Connection, file_path: str) -> None:
    cur = con.cursor()
    st = os.stat(file_path)
    from datetime import datetime, timezone
    mt = datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).replace(microsecond=0).isoformat()
    cur.execute(
        "insert or replace into api_imported_files(file_name, mtime_utc, imported_at) values(?,?,?)",
        (os.path.basename(file_path), mt, utcnow_iso()),
    )
    con.commit()


def parse_jsonl(path: str) -> List[Dict]:
    out: List[Dict] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                continue
    return out


def chunks(lst: List[str], n: int) -> Iterable[List[str]]:
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


def parse_iso8601_duration_to_seconds(s: Optional[str]) -> Optional[int]:
    # very small parser for PT#H#M#S
    if not s:
        return None
    import re

    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", s)
    if not m:
        return None
    h = int(m.group(1) or 0)
    m_ = int(m.group(2) or 0)
    s_ = int(m.group(3) or 0)
    return h * 3600 + m_ * 60 + s_


def fetch_videos(api_key: str, video_ids: List[str], qps: float = 1.0, session: Optional[requests.Session] = None) -> List[Dict]:
    if not video_ids:
        return []
    sess = session or requests.Session()
    url = API_URL
    params = {
        "part": "snippet,statistics,contentDetails",
        "id": ",".join(video_ids),
        "key": api_key,
        "maxResults": 50,
    }
    # QPS 制御（単純スリープ）
    time.sleep(max(0.0, 1.0 / max(qps, 0.1)))
    r = sess.get(url, params=params, timeout=30)
    r.raise_for_status()
    data = r.json()
    return data.get("items", [])


def save_snapshots(con: sqlite3.Connection, items: List[Dict], id_to_channel: Dict[str, str]) -> int:
    cur = con.cursor()
    now_iso = utcnow_iso()
    n = 0
    for it in items:
        vid = it.get("id")
        if not vid:
            continue
        snip = it.get("snippet", {})
        stats = it.get("statistics", {})
        cont = it.get("contentDetails", {})
        duration = parse_iso8601_duration_to_seconds(cont.get("duration")) or None
        ch_title = snip.get("channelTitle")
        vc = int(stats.get("viewCount", 0) or 0)
        lc = int(stats.get("likeCount", 0) or 0)
        cc = int(stats.get("commentCount", 0) or 0)
        category_id = snip.get("categoryId")
        live_flag = snip.get("liveBroadcastContent")
        ch = id_to_channel.get(vid)
        cur.execute(
            """
            insert into ytapi_snapshots(
              video_id, channel_id, channel_title, polled_at, view_count, like_count, comment_count, duration_seconds, category_id, live_broadcast_content
            ) values(?,?,?,?,?,?,?,?,?,?)
            """,
            (vid, ch, ch_title, now_iso, vc, lc, cc, duration, category_id, live_flag),
        )
        n += 1
    con.commit()
    return n


def run_once(
    db_path: str,
    in_dir: str,
    api_key: str,
    only_new_files: bool = True,
    batch_size: int = 50,
    qps: float = 1.0,
    max_files: Optional[int] = None,
) -> int:
    con = open_db(db_path)
    files = list_unprocessed(in_dir, con) if only_new_files else sorted(glob(os.path.join(in_dir, "rss_discovered_*.jsonl")))
    if max_files:
        files = files[:max_files]
    if not files:
        print("No input files to process.")
        return 0
    sess = requests.Session()
    total_vids = 0
    for fp in files:
        rows = parse_jsonl(fp)
        # video_id をユニーク化し、channel_id のマップを作る
        id_to_channel: Dict[str, str] = {}
        vids: List[str] = []
        for r in rows:
            vid = r.get("video_id")
            if not vid:
                continue
            if vid not in id_to_channel:
                id_to_channel[vid] = r.get("channel_id")
                vids.append(vid)

        count = 0
        for chunk in chunks(vids, max(1, min(batch_size, 50))):
            try:
                items = fetch_videos(api_key, chunk, qps=qps, session=sess)
            except requests.HTTPError as e:
                print(f"HTTP error: {e}; ids={chunk}")
                # 軽いバックオフ
                time.sleep(5)
                continue
            except requests.RequestException as e:
                print(f"Request error: {e}")
                time.sleep(5)
                continue
            count += save_snapshots(con, items, id_to_channel)
        print(f"Processed {os.path.basename(fp)}: videos={len(vids)}, saved={count}")
        total_vids += len(vids)
        mark_processed(con, fp)
    return total_vids


def build_arg_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Fetch YouTube video stats into snapshots")
    ap.add_argument("--db", default="data/rss_watch.sqlite", help="RSS連携DB (rss_watch.sqlite)")
    ap.add_argument("--in-dir", default="exports", help="NDJSON入力ディレクトリ")
    ap.add_argument("--api-key", default=os.getenv("YOUTUBE_API_KEY"), help="YouTube API key (env YOUTUBE_API_KEY)")
    ap.add_argument("--batch-size", type=int, default=50, help="videos.list の 1 リクエスト本数 (<=50)")
    ap.add_argument("--qps", type=float, default=1.0, help="毎秒リクエスト数の上限")
    ap.add_argument("--all-files", action="store_true", help="未処理限定でなく全ファイルを処理")
    ap.add_argument("--max-files", type=int, default=0, help="処理ファイル数の上限（0=無制限）")
    return ap


def main(argv: Optional[List[str]] = None) -> int:
    ap = build_arg_parser()
    args = ap.parse_args(argv)
    if not args.api_key:
        print("ERROR: --api-key 未指定か、環境変数 YOUTUBE_API_KEY が設定されていません。")
        return 2
    return run_once(
        db_path=args.db,
        in_dir=args.in_dir,
        api_key=args.api_key,
        only_new_files=(not args.all_files),
        batch_size=args.batch_size,
        qps=args.qps,
        max_files=(args.max_files or None),
    )


if __name__ == "__main__":
    raise SystemExit(main())
