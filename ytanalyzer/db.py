# -*- coding: utf-8 -*-
import sqlite3, os, logging
from contextlib import closing
from typing import Any, Iterable

logger = logging.getLogger(__name__)

SCHEMA_SQL = """
PRAGMA journal_mode = WAL;
CREATE TABLE IF NOT EXISTS channels (
  channel_id INTEGER PRIMARY KEY,
  detail_url TEXT, list_page INTEGER, ban_date TEXT,
  channel_name TEXT, is_suspended INTEGER,
  subs INTEGER, views INTEGER, videos INTEGER, opened_on TEXT,
  tags TEXT, auto_tags TEXT, page_text TEXT,
  shorts_ratio TEXT, scraped_at TEXT, debug_note TEXT,
  ban_reason_ai TEXT
);
CREATE TABLE IF NOT EXISTS videos (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  channel_id INTEGER, detail_url TEXT, latest_url TEXT, video_rank INTEGER,
  video_title TEXT, video_url TEXT,
  video_views INTEGER, video_views_tx TEXT,
  video_likes INTEGER, published_at TEXT, published_tx TEXT,
  scraped_at TEXT,
  UNIQUE(channel_id, video_url)
);
CREATE INDEX IF NOT EXISTS idx_channels_date ON channels(ban_date);
CREATE INDEX IF NOT EXISTS idx_channels_name ON channels(channel_name);

CREATE TABLE IF NOT EXISTS ban_channels (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  channel_name TEXT, channel_url TEXT,
  ban_date TEXT, description TEXT, reason TEXT,
  category TEXT, severity TEXT,
  scraped_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_ban_channels_date ON ban_channels(ban_date);

CREATE TABLE IF NOT EXISTS ban_reasons (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  channel_name TEXT, category TEXT, confidence REAL,
  reasoning TEXT, keywords TEXT, classified_at TEXT
);

CREATE TABLE IF NOT EXISTS video_snapshots (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  video_id TEXT, channel_id INTEGER,
  date TEXT, view_count INTEGER, like_count INTEGER, comment_count INTEGER
);
"""

def migrate_schema(con: sqlite3.Connection) -> None:
    def cols(t:str): 
        return {r[1] for r in con.execute(f"PRAGMA table_info({t})")}
    need_ch={"tags":"TEXT","auto_tags":"TEXT","page_text":"TEXT","shorts_ratio":"TEXT",
             "subs":"INTEGER","views":"INTEGER","videos":"INTEGER","opened_on":"TEXT",
             "channel_name":"TEXT","ban_date":"TEXT","debug_note":"TEXT",
             "ban_reason_ai":"TEXT"}
    need_vi={"video_views_tx":"TEXT","published_tx":"TEXT","video_likes":"INTEGER"}
    for n,t in need_ch.items():
        if n not in cols("channels"): con.execute(f"ALTER TABLE channels ADD COLUMN {n} {t};")
    for n,t in need_vi.items():
        if n not in cols("videos"): con.execute(f"ALTER TABLE videos ADD COLUMN {n} {t};")
    con.commit()

class Database:
    def __init__(self, path: str = "data/yutura.sqlite"):
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self.path = path
        self._init()

    def _init(self):
        with sqlite3.connect(self.path, timeout=60) as con:
            with closing(con.cursor()) as cur:
                cur.executescript(SCHEMA_SQL)
            migrate_schema(con)

    def connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.path, timeout=60, check_same_thread=False)
        con.row_factory = sqlite3.Row
        return con

    def execute(self, sql: str, params: Iterable[Any] = ()):
        with self.connect() as con:
            with closing(con.cursor()) as cur:
                cur.execute(sql, params)
                con.commit()
                return cur

    def query(self, sql: str, params: Iterable[Any] = ()):
        with self.connect() as con:
            with closing(con.cursor()) as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()
                return rows
