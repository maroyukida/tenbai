import os
import sys
import sqlite3
from datetime import datetime

# Ensure project root on path
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from ytanalyzer.config import Config


def main():
    cfg = Config()
    path = cfg.rss_db_path
    print(f"rss_db_path: {path} (exists={os.path.exists(path)})")
    con = sqlite3.connect(path)
    cur = con.cursor()

    def show_latest(table: str, ts_col: str = "published_at"):
        try:
            cnt = cur.execute(f"select count(*) from {table}").fetchone()[0]
            latest = cur.execute(f"select max({ts_col}) from {table}").fetchone()[0]
            print(f"{table}: count={cnt}, latest_{ts_col}={latest}")
        except Exception as e:
            print(f"{table} err: {e}")

    # Key tables
    show_latest("trending_ranks")
    show_latest("rss_videos")
    # Try alternative timestamp columns for snapshots/metrics
    for col in ("fetched_at", "polled_at", "updated_at"):
        try:
            show_latest("ytapi_snapshots", ts_col=col)
            break
        except Exception:
            continue
    for col in ("computed_at", "updated_at"):
        try:
            show_latest("growth_metrics", ts_col=col)
            break
        except Exception:
            continue

    # Columns of key tables
    print("columns:")
    for t in ("rss_videos", "ytapi_snapshots", "trending_ranks", "rss_videos_discovered"):
        try:
            cols = [r[1] for r in cur.execute(f"pragma table_info({t})").fetchall()]
            print(f"  {t}: {', '.join(cols)}")
        except Exception as e:
            print(f"  {t} err: {e}")

    # Recent activity in last 60 minutes
    def since_1h(table: str, col: str) -> int:
        try:
            sql = (
                f"select count(*) from {table} "
                f"where strftime('%s',replace(substr({col},1,19),'T',' '))>=strftime('%s','now','-1 hour')"
            )
            return int(cur.execute(sql).fetchone()[0])
        except Exception:
            return -1

    print("last_1h:")
    for col in ("discovered_at", "created_at", "updated_at"):
        n = since_1h("rss_videos", col)
        if n >= 0:
            print(f"  rss_videos.{col}: {n}")
            break
    for col in ("polled_at", "updated_at", "fetched_at"):
        n = since_1h("ytapi_snapshots", col)
        if n >= 0:
            print(f"  ytapi_snapshots.{col}: {n}")
            break
    for col in ("updated_at", "published_at"):
        n = since_1h("trending_ranks", col)
        if n >= 0:
            print(f"  trending_ranks.{col}: {n}")
            break
    for col in ("discovered_at", "created_at"):
        n = since_1h("rss_videos_discovered", col)
        if n >= 0:
            print(f"  rss_videos_discovered.{col}: {n}")
            break

    con.close()


if __name__ == "__main__":
    main()
