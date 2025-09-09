# -*- coding: utf-8 -*-
from __future__ import annotations

import sqlite3
import json
import sys


def main(db: str = "data/rss_watch.sqlite") -> int:
    con = sqlite3.connect(db)
    cur = con.cursor()
    q_recent = (
        "select count(*) from rss_videos_discovered "
        "where strftime('%s', replace(substr(discovered_at,1,19),'T',' ')) >= strftime('%s','now','-48 hours')"
    )
    q_with_snap = (
        "select count(distinct d.video_id) from rss_videos_discovered d "
        "join ytapi_snapshots s on s.video_id=d.video_id "
        "where strftime('%s', replace(substr(d.discovered_at,1,19),'T',' ')) >= strftime('%s','now','-48 hours')"
    )
    recent = cur.execute(q_recent).fetchone()[0]
    with_snap = cur.execute(q_with_snap).fetchone()[0]
    tr_count = cur.execute("select count(*) from trending_ranks").fetchone()[0]
    print(json.dumps({
        "recent_48h_discovered": int(recent),
        "with_snapshots": int(with_snap),
        "trending_ranks": int(tr_count),
    }))
    con.close()
    return 0


if __name__ == "__main__":
    db = sys.argv[1] if len(sys.argv) > 1 else "data/rss_watch.sqlite"
    raise SystemExit(main(db))

