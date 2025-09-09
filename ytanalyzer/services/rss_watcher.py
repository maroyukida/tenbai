# -*- coding: utf-8 -*-
"""
YouTube RSS watcher (大規模チャンネル巡回で新着検出)

機能:
- 各チャンネルの RSS (https://www.youtube.com/feeds/videos.xml?channel_id=UC...) をポーリング
- ETag / Last-Modified を活用し 304 多発で帯域節約
- next_poll_at による適応スケジューリング（活動度・失敗回数で間隔を動的調整）
- 429/5xx などは指数バックオフ + ジッタ
- inflight 予約で二重投入防止
- RPS（毎秒の最大リクエスト数）をトークンバケットで制御
- 進捗を JSON に書き出し（ミニダッシュボードで可視化）

使い方（例）:
  python -m ytanalyzer.services.rss_watcher --channels-file C:\\path\\yutura_channels.ndjson --once --limit 2000 --rps 10
  python -m ytanalyzer.services.rss_watcher --channels-file C:\\path\\yutura_channels.ndjson --concurrency 200 --rps 15 --batch 800 --tick 5

CLI 統合（ytanalyzer.cli から）:
  python -m ytanalyzer.cli rss-watch --channels-file C:\\path\\yutura_channels.ndjson --rps 15
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import sqlite3
import time
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Tuple

import httpx
import feedparser


UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36"
)
HEADERS_BASE = {
    "User-Agent": UA,
    "Accept": "application/atom+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ja-JP,ja;q=0.9,en;q=0.7",
    "Cache-Control": "no-cache",
}

# 既存 DB とテーブル名衝突を避けるため、別 DB ファイルを既定にする
DB_DEFAULT = os.path.join("data", "rss_watch.sqlite")
# 進捗 JSON は data/ 配下に出力（ダッシュボードは data/rss_progress.json を参照）
PROGRESS_JSON = os.path.join("data", "rss_progress.json")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _utciso() -> str:
    return _utcnow().replace(microsecond=0).isoformat()


def ensure_db(db: str) -> sqlite3.Connection:
    os.makedirs(os.path.dirname(db) or ".", exist_ok=True)
    con = sqlite3.connect(db, timeout=60)
    # テーブル名は衝突回避のため接頭辞 rss_
    con.execute("pragma journal_mode=WAL;")
    con.execute(
        """
        create table if not exists rss_videos(
          video_id text primary key,
          channel_id text,
          title text,
          published_at text,
          length_seconds integer,
          is_shorts integer,
          canonical_url text,
          thumb_hq text,
          thumb_maxres text,
          category text,
          keywords_json text,
          description_snip text,
          is_unlisted integer,
          is_age_restricted integer,
          is_live integer,
          live_start text,
          live_end text,
          captions_json text,
          chapters_json text,
          subtitle_text text
        )
        """
    )
    con.execute(
        """
        create table if not exists rss_videos_discovered(
          video_id text primary key,
          channel_id text,
          title text,
          published_at text,
          discovered_at text
        )
        """
    )
    con.execute(
        """
        create table if not exists rss_channels(
          channel_id text primary key,
          etag text,
          last_modified text,
          last_checked_at text,
          last_success_at text,
          last_http_status integer,
          failures integer default 0,
          next_poll_at text,
          poll_interval_sec integer,
          last_seen_published text,
          last_seen_video_id text,
          inflight integer default 0,
          disabled integer default 0
        )
        """
    )
    con.commit()
    return con


def extract_ucid_from_url(url: str) -> Optional[str]:
    if not isinstance(url, str):
        return None
    for part in url.split('/'):
        if part.startswith("UC"):
            return part
    return None


def seed_channels(con: sqlite3.Connection, ndjson_path: str) -> int:
    ucids = set()
    with open(ndjson_path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            url = row.get("youtube_channel_url") or row.get("channel_url") or row.get("url")
            if not url:
                continue
            ucid = extract_ucid_from_url(url)
            if ucid:
                ucids.add(ucid)

    cur = con.cursor()
    rows = []
    now = _utcnow()
    for u in ucids:
        jitter = timedelta(seconds=random.randint(0, 600))
        rows.append(
            (
                u,
                None,
                None,
                None,
                None,
                None,
                0,
                (now + jitter).replace(microsecond=0).isoformat(),
                3600,
                None,
                None,
                0,
                0,
            )
        )
    cur.executemany(
        """
        insert or ignore into rss_channels(
          channel_id, etag, last_modified, last_checked_at, last_success_at, last_http_status,
          failures, next_poll_at, poll_interval_sec, last_seen_published, last_seen_video_id, inflight, disabled
        ) values(?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        rows,
    )
    con.commit()
    return len(ucids)


def reserve_due_channels(con: sqlite3.Connection, limit: int) -> List[Dict[str, Any]]:
    """next_poll_at <= now かつ inflight=0 を予約し取り出す"""
    now = _utciso()
    cur = con.cursor()
    cur.execute(
        """
        select channel_id, etag, last_modified, poll_interval_sec
        from rss_channels
        where disabled=0 and inflight=0 and (next_poll_at is null or next_poll_at <= ?)
        order by next_poll_at asc
        limit ?
        """,
        (now, limit),
    )
    rows = cur.fetchall()
    if not rows:
        return []
    ids = [r[0] for r in rows]
    qmarks = ",".join("?" * len(ids))
    cur.execute(f"update rss_channels set inflight=1 where channel_id in ({qmarks})", ids)
    con.commit()
    cols = ["channel_id", "etag", "last_modified", "poll_interval_sec"]
    return [dict(zip(cols, r)) for r in rows]


def upsert_video(
    con: sqlite3.Connection,
    vid: str,
    cid: str,
    title: Optional[str],
    published_at: Optional[str],
) -> bool:
    thumb_hq = f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"
    thumb_max = f"https://i.ytimg.com/vi/{vid}/maxresdefault.jpg"
    cur = con.cursor()
    cur.execute(
        """
        insert or ignore into rss_videos(video_id, channel_id, title, published_at, thumb_hq, thumb_maxres)
        values(?,?,?,?,?,?)
        """,
        (vid, cid, title, published_at, thumb_hq, thumb_max),
    )
    inserted1 = cur.rowcount > 0
    cur.execute(
        """
        insert or ignore into rss_videos_discovered(video_id, channel_id, title, published_at, discovered_at)
        values(?,?,?,?,?)
        """,
        (vid, cid, title, published_at, _utciso()),
    )
    inserted2 = cur.rowcount > 0
    con.commit()
    return inserted1 or inserted2


def finalize_channel(
    con: sqlite3.Connection,
    cid: str,
    next_iv: int,
    http_status: Optional[int],
    etag: Optional[str],
    last_modified: Optional[str],
    last_seen_published: Optional[str],
    last_seen_video_id: Optional[str],
) -> None:
    cur = con.cursor()
    next_at = (_utcnow() + timedelta(seconds=next_iv)).replace(microsecond=0).isoformat()
    cur.execute(
        """
        update rss_channels
        set etag=coalesce(?,etag),
            last_modified=coalesce(?,last_modified),
            last_checked_at=?,
            last_success_at=case when ? between 200 and 299 or ?=304 then ? else last_success_at end,
            last_http_status=?,
            failures=case when ? between 200 and 299 or ?=304 then 0 else failures end,
            last_seen_published=coalesce(?, last_seen_published),
            last_seen_video_id=coalesce(?, last_seen_video_id),
            next_poll_at=?,
            poll_interval_sec=?,
            inflight=0
        where channel_id=?
        """,
        (
            etag,
            last_modified,
            _utciso(),
            http_status,
            http_status,
            _utciso(),
            http_status,
            http_status,
            http_status,
            last_seen_published,
            last_seen_video_id,
            next_at,
            next_iv,
            cid,
        ),
    )
    con.commit()


def mark_error(con: sqlite3.Connection, cid: str, http_status: Optional[int], backoff: int) -> None:
    cur = con.cursor()
    next_at = (_utcnow() + timedelta(seconds=backoff)).replace(microsecond=0).isoformat()
    cur.execute(
        """
        update rss_channels
        set failures = coalesce(failures,0)+1,
            last_checked_at=?,
            last_http_status=?,
            next_poll_at=?,
            inflight=0
        where channel_id=?
        """,
        (_utciso(), http_status, next_at, cid),
    )
    con.commit()


def compute_next_interval(
    base_interval: int,
    had_new: bool,
    failures: int,
    last_seen_pub_iso: Optional[str],
) -> int:
    # 失敗時: 指数バックオフ（最大 6h）＋ジッタ
    if failures > 0:
        base = 300  # 5min
        iv = min(6 * 3600, int(base * (1.9 ** min(failures, 6))))
        return int(iv * random.uniform(0.8, 1.2))
    # 新着あり: 5〜15分
    if had_new:
        return int(random.uniform(300, 900))
    # 直近の活動度で階層化
    if not last_seen_pub_iso:
        return int((base_interval or 3600) * random.uniform(0.8, 1.2))
    try:
        last_pub = (
            datetime.fromisoformat(last_seen_pub_iso.replace("Z", ""))
            .replace(tzinfo=timezone.utc)
        )
    except Exception:
        return int((base_interval or 3600) * random.uniform(0.8, 1.2))
    age = (_utcnow() - last_pub).total_seconds()
    if age < 24 * 3600:
        return int(900 * random.uniform(0.8, 1.2))  # 15分
    elif age < 7 * 24 * 3600:
        return int(1800 * random.uniform(0.8, 1.2))  # 30分
    elif age < 30 * 24 * 3600:
        return int(7200 * random.uniform(0.8, 1.2))  # 2時間
    else:
        return int(12 * 3600 * random.uniform(0.8, 1.2))  # 12時間


def parse_entries(text: str) -> List[Dict[str, Any]]:
    f = feedparser.parse(text)
    entries = []
    for e in f.entries:
        vid = getattr(e, "yt_videoid", None) or getattr(e, "id", None)
        published = getattr(e, "published", None)
        title = getattr(e, "title", None)
        if vid:
            entries.append({"video_id": vid, "published": published, "title": title})
    # 古い→新しい
    return list(reversed(entries))


class RateLimiter:
    """単純なトークンバケット（毎秒 RPS）"""

    def __init__(self, rps: float):
        self.rps = max(1.0, float(rps))
        self.tokens = self.rps
        self.last = time.monotonic()
        self.lock = asyncio.Lock()

    async def acquire(self):
        async with self.lock:
            now = time.monotonic()
            elapsed = now - self.last
            self.tokens = min(self.rps, self.tokens + elapsed * self.rps)
            if self.tokens < 1.0:
                await asyncio.sleep((1.0 - self.tokens) / self.rps)
                now = time.monotonic()
                elapsed = now - self.last
                self.tokens = min(self.rps, self.tokens + elapsed * self.rps)
            self.tokens -= 1.0
            self.last = time.monotonic()


async def fetch_feed(
    client: httpx.AsyncClient,
    limiter: RateLimiter,
    cid: str,
    etag: Optional[str],
    last_modified: Optional[str],
) -> Tuple[int, Optional[httpx.Response]]:
    await limiter.acquire()
    url = f"https://www.youtube.com/feeds/videos.xml?channel_id={cid}"
    headers = dict(HEADERS_BASE)
    if etag:
        headers["If-None-Match"] = etag
    if last_modified:
        headers["If-Modified-Since"] = last_modified
    try:
        r = await client.get(url, headers=headers, timeout=20.0)
        return r.status_code, r
    except httpx.HTTPError:
        return 0, None


async def worker_loop(
    client: httpx.AsyncClient,
    limiter: RateLimiter,
    con: sqlite3.Connection,
    taskq: asyncio.Queue,
    stats: Dict[str, int],
):
    while True:
        item = await taskq.get()
        if item is None:
            taskq.task_done()
            return
        cid = item["channel_id"]
        etag = item.get("etag")
        last_mod = item.get("last_modified")
        base_iv = item.get("poll_interval_sec") or 3600

        status, resp = await fetch_feed(client, limiter, cid, etag, last_mod)
        if status == 304:
            stats["not_modified"] += 1
            cur = con.cursor()
            cur.execute(
                "select failures, last_seen_published from rss_channels where channel_id=?",
                (cid,),
            )
            row = cur.fetchone() or [0, None]
            next_iv = compute_next_interval(base_iv, False, 0, row[1])
            finalize_channel(
                con,
                cid,
                next_iv,
                304,
                resp.headers.get("ETag") if resp is not None else None,
                resp.headers.get("Last-Modified") if resp is not None else None,
                None,
                None,
            )
        elif status == 200 and resp is not None:
            stats["ok"] += 1
            entries = parse_entries(resp.text)
            had_new = False
            last_seen_vid, last_seen_pub = None, None
            for ent in entries:
                v = ent["video_id"]
                p = ent.get("published")
                t = ent.get("title")
                if upsert_video(con, v, cid, t, p):
                    had_new = True
                last_seen_vid, last_seen_pub = v, p
            next_iv = compute_next_interval(base_iv, had_new, 0, last_seen_pub)
            finalize_channel(
                con,
                cid,
                next_iv,
                200,
                resp.headers.get("ETag"),
                resp.headers.get("Last-Modified"),
                last_seen_pub,
                last_seen_vid,
            )
            if had_new:
                stats["new_videos"] += 1
        elif status in (403, 404, 410):
            stats["gone"] += 1
            mark_error(con, cid, status, backoff=24 * 3600)
        elif status == 429:
            stats["blocked"] += 1
            mark_error(con, cid, status, backoff=int(15 * 60 * random.uniform(0.8, 1.2)))
        else:
            stats["error"] += 1
            cur = con.cursor()
            cur.execute("select failures from rss_channels where channel_id=?", (cid,))
            fails = (cur.fetchone() or [0])[0] or 0
            backoff = compute_next_interval(3600, False, fails + 1, None)
            mark_error(con, cid, status, backoff=backoff)
        taskq.task_done()


def write_progress(con: sqlite3.Connection, last_stats: Dict[str, int]) -> None:
    os.makedirs(os.path.dirname(PROGRESS_JSON) or ".", exist_ok=True)
    cur = con.cursor()
    cur.execute("select count(*) from rss_channels")
    total = cur.fetchone()[0]
    cur.execute("select count(*) from rss_videos_discovered")
    discovered = cur.fetchone()[0]
    cur.execute("select count(*) from rss_videos")
    videos = cur.fetchone()[0]
    cur.execute("select count(*) from rss_channels where inflight=0 and (next_poll_at <= ?)", (_utciso(),))
    due = cur.fetchone()[0]
    data = {
        "updated_at": _utciso(),
        "total_channels": total,
        "due_now": due,
        "videos_table_count": videos,
        "discovered_queue_count": discovered,
        "last_batch": last_stats,
    }
    with open(PROGRESS_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


async def run_once(
    con: sqlite3.Connection,
    channels_file: str,
    concurrency: int,
    rps: float,
    limit: int,
):
    seed_channels(con, channels_file)
    due = reserve_due_channels(con, limit or concurrency * 4)
    stats = {"ok": 0, "not_modified": 0, "new_videos": 0, "blocked": 0, "gone": 0, "error": 0}
    limits = httpx.Limits(max_connections=concurrency, max_keepalive_connections=concurrency)
    limiter = RateLimiter(rps)
    async with httpx.AsyncClient(http2=True, headers=HEADERS_BASE, limits=limits, timeout=20.0) as client:
        q: asyncio.Queue = asyncio.Queue()
        workers = [asyncio.create_task(worker_loop(client, limiter, con, q, stats)) for _ in range(concurrency)]
        for it in due:
            await q.put(it)
        for _ in range(concurrency):
            await q.put(None)
        await q.join()
        for w in workers:
            await w
    write_progress(con, stats)


async def run_daemon(
    con: sqlite3.Connection,
    channels_file: str,
    concurrency: int,
    rps: float,
    batch_size: int,
    tick_sec: int,
):
    seed_channels(con, channels_file)
    stats = {"ok": 0, "not_modified": 0, "new_videos": 0, "blocked": 0, "gone": 0, "error": 0}
    limits = httpx.Limits(max_connections=concurrency, max_keepalive_connections=concurrency)
    limiter = RateLimiter(rps)
    async with httpx.AsyncClient(http2=True, headers=HEADERS_BASE, limits=limits, timeout=20.0) as client:
        q: asyncio.Queue = asyncio.Queue()
        workers = [asyncio.create_task(worker_loop(client, limiter, con, q, stats)) for _ in range(concurrency)]
        try:
            while True:
                if q.qsize() < batch_size:
                    for it in reserve_due_channels(con, batch_size - q.qsize()):
                        await q.put(it)
                await asyncio.sleep(tick_sec)
                write_progress(con, stats)
        finally:
            for _ in range(concurrency):
                await q.put(None)
            await q.join()
            for w in workers:
                await w


def build_arg_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="YouTube RSS watcher (大規模新着検出)")
    ap.add_argument("--channels-file", required=True, help="yutura 形式 NDJSON (youtube_channel_url を含む)")
    ap.add_argument("--db", default=DB_DEFAULT, help=f"SQLite DB パス (default: {DB_DEFAULT})")
    ap.add_argument("--concurrency", type=int, default=200)
    ap.add_argument("--rps", type=float, default=15.0, help="1 秒あたりの最大リクエスト数")
    ap.add_argument("--batch", type=int, default=800, help="1 tick で投入最大件数")
    ap.add_argument("--tick", type=int, default=5, help="tick 秒数（投入間隔）")
    ap.add_argument("--once", action="store_true", help="1 バッチだけ実行して終了")
    ap.add_argument("--limit", type=int, default=0, help="--once 時の最大処理件数")
    return ap


def main(argv: Optional[List[str]] = None) -> None:
    ap = build_arg_parser()
    args = ap.parse_args(argv)
    con = ensure_db(args.db)
    if args.once:
        asyncio.run(run_once(con, args.channels_file, args.concurrency, args.rps, args.limit))
    else:
        asyncio.run(run_daemon(con, args.channels_file, args.concurrency, args.rps, args.batch, args.tick))


if __name__ == "__main__":
    main()

