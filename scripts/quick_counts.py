import os
import sys
import sqlite3

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from ytanalyzer.config import Config


def main():
    cfg = Config()
    path = cfg.rss_db_path
    con = sqlite3.connect(path)
    cur = con.cursor()
    tables = [
        "rss_videos",
        "ytapi_snapshots",
        "trending_ranks",
        "rss_videos_discovered",
        "growth_metrics",
    ]
    for t in tables:
        try:
            n = cur.execute(f"select count(*) from {t}").fetchone()[0]
            print(f"{t}: {n}")
        except Exception as e:
            print(f"{t}: (missing) {e}")
    con.close()


if __name__ == "__main__":
    main()

