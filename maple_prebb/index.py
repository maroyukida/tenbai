from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Dict, Iterable, List, Optional


SCHEMA = [
    """
    CREATE TABLE IF NOT EXISTS pages (
      id INTEGER PRIMARY KEY,
      url TEXT,
      wayback_timestamp TEXT,
      status INTEGER,
      mimetype TEXT,
      digest TEXT,
      title TEXT,
      text TEXT,
      charset TEXT,
      meta_path TEXT,
      warc_path TEXT
    )
    """,
]

FTS5 = """
CREATE VIRTUAL TABLE IF NOT EXISTS pages_fts USING fts5(
  title, text, url, wayback_timestamp, content=''
)
"""


class Indexer:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.conn = sqlite3.connect(str(db_path))
        self.conn.execute("PRAGMA journal_mode=WAL")
        self._ensure_schema()

    def _ensure_schema(self):
        cur = self.conn.cursor()
        for stmt in SCHEMA:
            cur.execute(stmt)
        # Try FTS5
        try:
            cur.execute(FTS5)
            self.has_fts = True
        except sqlite3.OperationalError:
            self.has_fts = False
        self.conn.commit()

    def add(
        self,
        *,
        url: str,
        wayback_timestamp: str,
        status: Optional[int],
        mimetype: Optional[str],
        digest: Optional[str],
        title: str,
        text: str,
        charset: Optional[str],
        meta_path: Optional[str],
        warc_path: Optional[str],
    ) -> int:
        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT INTO pages(url, wayback_timestamp, status, mimetype, digest, title, text, charset, meta_path, warc_path)
            VALUES(?,?,?,?,?,?,?,?,?,?)
            """,
            (
                url,
                wayback_timestamp,
                status,
                mimetype,
                digest,
                title,
                text,
                charset,
                meta_path,
                warc_path,
            ),
        )
        rowid = cur.lastrowid
        if self.has_fts:
            cur.execute(
                "INSERT INTO pages_fts(rowid, title, text, url, wayback_timestamp) VALUES(?,?,?,?,?)",
                (rowid, title, text, url, wayback_timestamp),
            )
        self.conn.commit()
        return rowid

    def search(self, q: str, *, year: Optional[int] = None, limit: int = 20) -> List[Dict[str, str]]:
        cur = self.conn.cursor()

        def run_sql(sql: str, params: list) -> List[Dict[str, str]]:
            out: List[Dict[str, str]] = []
            for url, title, ts in cur.execute(sql, params):
                out.append({"url": url, "title": title, "wayback_timestamp": ts})
            return out

        # Prefer FTS; if it yields no results (common for CJK), fallback to LIKE
        if self.has_fts:
            sql = (
                "SELECT p.url, p.title, p.wayback_timestamp "
                "FROM pages p JOIN pages_fts f ON p.id=f.rowid "
                "WHERE pages_fts MATCH ?"
            )
            params: list = [q]
            if year:
                sql += " AND substr(p.wayback_timestamp,1,4)=?"
                params.append(str(year))
            sql += " LIMIT ?"
            params.append(int(limit))
            rows = run_sql(sql, params)
            if rows:
                return rows

        # LIKE fallback (handles Japanese better without tokenizer)
        sql = "SELECT url, title, wayback_timestamp FROM pages WHERE (title LIKE ? OR text LIKE ?)"
        params = [f"%{q}%", f"%{q}%"]
        if year:
            sql += " AND substr(wayback_timestamp,1,4)=?"
            params.append(str(year))
        sql += " LIMIT ?"
        params.append(int(limit))
        return run_sql(sql, params)

    def close(self):
        try:
            self.conn.close()
        except Exception:
            pass
