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
    con = sqlite3.connect(cfg.rss_db_path)
    cur = con.cursor()
    def q(sql: str):
        try:
            return cur.execute(sql).fetchone()[0]
        except Exception as e:
            return None

    total = q("select count(*) from ytapi_snapshots")
    min_ts = q("select min(polled_at) from ytapi_snapshots")
    max_ts = q("select max(polled_at) from ytapi_snapshots")
    last48 = q("select count(*) from ytapi_snapshots where strftime('%s',replace(substr(polled_at,1,19),'T',' '))>=strftime('%s','now','-48 hours')")
    uniq_vid_48 = q("select count(distinct video_id) from ytapi_snapshots where strftime('%s',replace(substr(polled_at,1,19),'T',' '))>=strftime('%s','now','-48 hours')")

    print(f"total={total}")
    print(f"min_polled_at={min_ts}")
    print(f"max_polled_at={max_ts}")
    print(f"last48h_count={last48}")
    print(f"last48h_unique_videos={uniq_vid_48}")
    con.close()


if __name__ == "__main__":
    main()

