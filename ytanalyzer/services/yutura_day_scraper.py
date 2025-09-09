# -*- coding: utf-8 -*-
from __future__ import annotations

"""
Yutura 日間ランキングのコピー（スクレイプ）

対象ページ例:
  https://yutura.net/ranking/day/?mode=view&date=YYYYMMDD
  （ページングがある場合は &page=2 ...）

取得項目（可能な範囲）:
  - rank（ページ上の並び順）
  - yutura_channel_id（/channel/{id}/ から抽出）
  - channel_name（リンクテキスト）
  - delta_views（見出しや近傍の「増加」数値を日本語表記から整数化; 不明ならNULL）
  - category / subs / views（取得できる場合のみ; 不明ならNULL）

保存先（SQLite; 既定: data/rss_watch.sqlite）:
  yutura_day_ranks(date TEXT, mode TEXT, rank INTEGER,
                   yutura_channel_id INTEGER, channel_name TEXT,
                   delta_views INTEGER, delta_subs INTEGER,
                   subs INTEGER, views INTEGER, category TEXT,
                   channel_url TEXT, captured_at TEXT,
                   PRIMARY KEY(date, mode, yutura_channel_id))

注意: 対象サイトの利用規約を遵守し、アクセス間隔・頻度を抑えてください。
"""

import argparse
import re
import sqlite3
from datetime import datetime, timezone
from typing import Dict, List, Optional

from ..scrapers.http import build_session, fetch_html
from bs4 import BeautifulSoup


BASE = "https://yutura.net/ranking/day/"


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def ensure_tables(con: sqlite3.Connection) -> None:
    con.execute(
        """
        create table if not exists yutora_day_ranks(
          date text,
          mode text,
          rank integer,
          yutura_channel_id integer,
          channel_name text,
          delta_views integer,
          delta_subs integer,
          subs integer,
          views integer,
          category text,
          channel_url text,
          captured_at text,
          primary key(date, mode, yutura_channel_id)
        )
        """
    )
    con.commit()


def parse_jp_number(s: str) -> Optional[int]:
    if not s:
        return None
    t = re.sub(r"[\s,]", "", s)
    t = t.replace("約", "")
    total = 0
    matched = False
    m = re.search(r"(\d+)億", t)
    if m:
        total += int(m.group(1)) * 100_000_000
        matched = True
    m = re.search(r"(\d+)万", t)
    if m:
        total += int(m.group(1)) * 10_000
        matched = True
        rest = t.split("万", 1)[1]
        mr = re.search(r"(\d+)", rest)
        if mr:
            total += int(mr.group(1))
    if matched:
        return total
    m = re.search(r"(\d{1,3}(?:,\d{3})+|\d+)", s)
    if m:
        try:
            return int(m.group(1).replace(",", ""))
        except Exception:
            return None
    return None


def extract_rows(html: str) -> List[Dict]:
    soup = BeautifulSoup(html, "lxml")
    items: List[Dict] = []
    # 戦略: /channel/{id}/ へのリンクを列挙し、近傍テキストから増加数などを推測
    rank = 0
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/channel/" not in href:
            continue
        try:
            chid = int(href.split("/channel/")[1].split("/")[0])
        except Exception:
            continue
        name = a.get_text(" ", strip=True) or None
        # 近傍テキストから日間増加（再生）を抽出
        delta_v = None
        parent = a.parent
        ctx_text = ""
        for _ in range(4):
            if not parent:
                break
            txt = parent.get_text(" ", strip=True)
            if txt and any(k in txt for k in ["増", "再生", "視聴", "登録", "+", "回"]):
                ctx_text = txt
                break
            parent = parent.parent
        # よくある表記例に幅広くマッチ
        m = re.search(r"([0-9,万億\s]+)\s*回\s*増|([0-9,万億\s]+)\s*増", ctx_text)
        if m:
            grp = m.group(1) or m.group(2) or ""
            delta_v = parse_jp_number(grp)
        rank += 1
        items.append({
            "rank": rank,
            "yutura_channel_id": chid,
            "channel_name": name,
            "delta_views": delta_v,
            "channel_url": href if href.startswith("http") else ("https://yutura.net" + href),
        })
    # 同一chid 重複を rank小さい順にユニーク化
    seen = set()
    uniq: List[Dict] = []
    for it in items:
        chid = it["yutura_channel_id"]
        if chid in seen:
            continue
        seen.add(chid)
        uniq.append(it)
    return uniq


def scrape_day(con: sqlite3.Connection, date_yyyymmdd: str, mode: str = "view", pages: int = 1) -> int:
    ensure_tables(con)
    s = build_session(use_cloudscraper=True)
    saved = 0
    for page in range(1, max(1, pages) + 1):
        # 2種類のURL形式に対応
        urls = [
            f"https://yutura.net/ranking/day/?mode={mode}&date={date_yyyymmdd}&page={page}",
            f"https://yutura.net/ranking/{mode}/daily/{date_yyyymmdd}/{page}",
        ]
        html = None
        for u in urls:
            try:
                html = fetch_html(s, u)
                break
            except Exception:
                html = None
                continue
        if not html:
            continue
        rows = extract_rows(html)
        cur = con.cursor()
        for it in rows:
            cur.execute(
                """
                insert into yutora_day_ranks(date, mode, rank, yutura_channel_id, channel_name, delta_views,
                                             delta_subs, subs, views, category, channel_url, captured_at)
                values(?,?,?,?,?,?,?,?,?,?,?,?)
                on conflict(date, mode, yutura_channel_id) do update set
                  rank=excluded.rank,
                  channel_name=excluded.channel_name,
                  delta_views=excluded.delta_views,
                  channel_url=excluded.channel_url,
                  captured_at=excluded.captured_at
                """,
                (
                    date_yyyymmdd, mode, it.get("rank"), it.get("yutura_channel_id"), it.get("channel_name"),
                    it.get("delta_views"), None, None, None, None, it.get("channel_url"), utcnow_iso(),
                ),
            )
            saved += 1
        con.commit()
    return saved


def build_arg_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Copy Yutura day ranking into local DB")
    ap.add_argument("--db", default="data/rss_watch.sqlite")
    ap.add_argument("--date", required=True, help="YYYYMMDD")
    ap.add_argument("--mode", default="view", help="view|subscriber など（サイトのmodeに一致）")
    ap.add_argument("--pages", type=int, default=3)
    return ap


def main(argv: Optional[List[str]] = None) -> int:
    ap = build_arg_parser()
    args = ap.parse_args(argv)
    con = sqlite3.connect(args.db, timeout=60)
    con.row_factory = sqlite3.Row
    n = scrape_day(con, args.date, args.mode, args.pages)
    print(f"saved {n} rows for {args.date} mode={args.mode}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

