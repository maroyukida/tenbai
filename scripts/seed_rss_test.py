# -*- coding: utf-8 -*-
from datetime import datetime, timezone, timedelta
import sqlite3, os

import sys
ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from ytanalyzer.services.rss_watcher import ensure_db


def iso(dt):
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def main():
    db = os.path.join("data", "rss_watch.sqlite")
    con = ensure_db(db)
    cur = con.cursor()

    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    # 3 つのテスト動画
    tests = [
        {
            # 窓内・採用される（published 1h 前）
            "video_id": "VID_TEST_1",
            "channel_id": "UC_TEST_1",
            "title": "テスト動画1",
            "published_at": now - timedelta(hours=1),
            "discovered_at": now - timedelta(minutes=2),
        },
        {
            # 窓内・published が 72h 前 → 既定の 48h フィルタで除外
            "video_id": "VID_TEST_2",
            "channel_id": "UC_TEST_2",
            "title": "テスト動画2(古い)",
            "published_at": now - timedelta(hours=72),
            "discovered_at": now - timedelta(minutes=9),
        },
        {
            # 窓外（discovered 12分前）→ 除外
            "video_id": "VID_TEST_3",
            "channel_id": "UC_TEST_3",
            "title": "テスト動画3(窓外)",
            "published_at": now - timedelta(hours=2),
            "discovered_at": now - timedelta(minutes=12),
        },
    ]

    for t in tests:
        cur.execute(
            """
            insert or ignore into rss_videos(video_id, channel_id, title, published_at)
            values(?,?,?,?)
            """,
            (t["video_id"], t["channel_id"], t["title"], iso(t["published_at"]))
        )
        cur.execute(
            """
            insert or ignore into rss_videos_discovered(video_id, channel_id, title, published_at, discovered_at)
            values(?,?,?,?,?)
            """,
            (t["video_id"], t["channel_id"], t["title"], iso(t["published_at"]), iso(t["discovered_at"]))
        )
    con.commit()
    print("seeded:")
    for t in tests:
        print(t["video_id"], iso(t["discovered_at"]), iso(t["published_at"]))


if __name__ == "__main__":
    main()
