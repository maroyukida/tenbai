# -*- coding: utf-8 -*-
from __future__ import annotations

"""
Rule+prior based video categorizer (AIなし)

Usage:
  # 最近の公開動画を対象（既定動作）
  python -m ytanalyzer.tools.categorizer --db data/rss_watch.sqlite --since-hours 6 \
      --rules config/categories.yml --limit 5000

  # トレンド上位N件を対象（表示上の即時反映向け）
  python -m ytanalyzer.tools.categorizer --db data/rss_watch.sqlite --rules config/categories.yml \
      --trending-top 1000

Creates/updates tables:
  - video_categories(video_id primary key, primary_label, secondary_labels_json,
                     confidence, matched_keywords_json, updated_at)
  - channel_category_prior(channel_id primary key, primary_label, labels_json,
                           confidence, sample_size, updated_at)
"""

import argparse
import json
import os
import re
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

import yaml


UTC = timezone.utc


def utcnow_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def open_db(path: str) -> sqlite3.Connection:
    con = sqlite3.connect(path, timeout=60)
    con.row_factory = sqlite3.Row
    return con


class Rules:
    def __init__(self, data: dict):
        self.categories: List[dict] = data.get("categories", [])
        self.excludes_global: List[str] = data.get("excludes_global", [])
        # pre-compile
        for c in self.categories:
            c["_inc"] = [re.compile(p, re.I) for p in c.get("includes", [])]
            c["_exc"] = [re.compile(p, re.I) for p in c.get("excludes", [])]
            w = c.get("weight") or {}
            c["_w_title"] = int(w.get("title", 2))
            c["_w_tags"] = int(w.get("tags", 2))
            c["_w_desc"] = int(w.get("desc", 1))
            c["_thr"] = int(c.get("threshold", 6))
        self._gexc = [re.compile(p, re.I) for p in self.excludes_global]

    @staticmethod
    def load(path: str) -> "Rules":
        with open(path, "r", encoding="utf-8") as f:
            return Rules(yaml.safe_load(f))


def normalize_text(s: Optional[str]) -> str:
    if not s:
        return ""
    s = str(s)
    # 軽い正規化: 改行/タブ→空白、複数空白を1つ
    s = re.sub(r"[\t\r\n]+", " ", s)
    s = re.sub(r"\s{2,}", " ", s).strip()
    return s


def parse_tags(tags_json: Optional[str]) -> List[str]:
    if not tags_json:
        return []
    try:
        arr = json.loads(tags_json)
        if isinstance(arr, list):
            return [str(x) for x in arr if x]
    except Exception:
        pass
    return []


def rule_score(cat: dict, title: str, tags: List[str], desc: str) -> Tuple[int, List[str]]:
    score = 0
    hits: List[str] = []
    for rx in cat["_exc"]:
        if rx.search(title) or rx.search(desc) or any(rx.search(t) for t in tags):
            return 0, hits
    for rx in cat["_inc"]:
        if rx.search(title):
            score += cat["_w_title"]
            hits.append(f"title:{rx.pattern}")
        if any(rx.search(t) for t in tags):
            score += cat["_w_tags"]
            hits.append(f"tags:{rx.pattern}")
        if rx.search(desc):
            score += cat["_w_desc"]
            hits.append(f"desc:{rx.pattern}")
    for g in cat.get("_gexc", []):
        if g.search(title) or g.search(desc):
            return 0, hits
    return score, hits


def get_prior(con: sqlite3.Connection, channel_id: Optional[str]) -> Dict[str, float]:
    if not channel_id:
        return {}
    row = con.execute(
        "select labels_json from channel_category_prior where channel_id=?",
        (channel_id,),
    ).fetchone()
    if row and row[0]:
        try:
            d = json.loads(row[0])
            return {str(k): float(v) for k, v in d.items()}
        except Exception:
            return {}
    return {}


def decide_category(
    rules: Rules,
    con: sqlite3.Connection,
    title: str,
    tags: List[str],
    desc: str,
    channel_id: Optional[str],
    alpha: float = 1.0,
    beta: float = 0.5,
) -> Tuple[Optional[str], List[str], float, List[str]]:
    # ルールスコア
    scores: Dict[str, float] = {}
    matched: Dict[str, List[str]] = defaultdict(list)
    for c in rules.categories:
        s, hits = rule_score(c, title, tags, desc)
        if s > 0:
            scores[c["name"]] = s
            matched[c["name"]] += hits
    # prior
    prior = get_prior(con, channel_id)
    for k, v in prior.items():
        scores[k] = scores.get(k, 0.0) * alpha + v * beta

    if not scores:
        return None, [], 0.0, []
    # top
    sorted_cats = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    top1, top1_s = sorted_cats[0]
    top2_s = sorted_cats[1][1] if len(sorted_cats) >= 2 else 0.0
    conf = float(max(0.0, top1_s - top2_s))
    # threshold: use per-category or default 5
    thr_map = {c["name"]: c["_thr"] for c in rules.categories}
    if top1_s < thr_map.get(top1, 5):
        return None, [], 0.0, []
    # secondary up to 2
    secs = [k for k, s in sorted_cats[1:3] if s > 0]
    return top1, secs, conf, matched.get(top1, [])


def ensure_tables(con: sqlite3.Connection) -> None:
    cur = con.cursor()
    cur.execute(
        """
        create table if not exists video_categories(
          video_id text primary key,
          primary_label text,
          secondary_labels_json text,
          confidence real,
          matched_keywords_json text,
          updated_at text
        )
        """
    )
    cur.execute(
        """
        create table if not exists channel_category_prior(
          channel_id text primary key,
          primary_label text,
          labels_json text,
          confidence real,
          sample_size integer,
          updated_at text
        )
        """
    )
    con.commit()


def fetch_recent_videos(con: sqlite3.Connection, since_hours: int, limit: int) -> List[sqlite3.Row]:
    cur = con.cursor()
    # 直近 since_hours の新規/更新を対象（rss_videos起点）
    rows = cur.execute(
        """
        select v.video_id, v.channel_id, v.title, v.keywords_json, v.description_snip
        from rss_videos v
        where strftime('%s', replace(substr(coalesce(v.published_at, ''),1,19),'T',' ')) >= strftime('%s','now', ?)
        order by coalesce(v.published_at, '') desc
        limit ?
        """,
        (f"-{int(since_hours)} hours", limit),
    ).fetchall()
    return rows


def fetch_trending_top(con: sqlite3.Connection, top_n: int) -> List[sqlite3.Row]:
    cur = con.cursor()
    # trending_ranks のスコア上位を対象に、rss_videos の本文情報で分類する
    rows = cur.execute(
        """
        select v.video_id, v.channel_id, v.title, v.keywords_json, v.description_snip
        from trending_ranks tr
        join rss_videos v on v.video_id = tr.video_id
        order by tr.score desc, tr.current_views desc
        limit ?
        """,
        (int(top_n),),
    ).fetchall()
    return rows


def upsert_video_category(
    con: sqlite3.Connection,
    video_id: str,
    primary_label: Optional[str],
    secondary: List[str],
    confidence: float,
    matched: List[str],
) -> None:
    cur = con.cursor()
    cur.execute(
        """
        insert into video_categories(video_id, primary_label, secondary_labels_json, confidence, matched_keywords_json, updated_at)
        values(?,?,?,?,?,?)
        on conflict(video_id) do update set
          primary_label=excluded.primary_label,
          secondary_labels_json=excluded.secondary_labels_json,
          confidence=excluded.confidence,
          matched_keywords_json=excluded.matched_keywords_json,
          updated_at=excluded.updated_at
        """,
        (
            video_id,
            primary_label,
            json.dumps(secondary, ensure_ascii=False),
            float(confidence),
            json.dumps(matched, ensure_ascii=False),
            utcnow_iso(),
        ),
    )
    con.commit()


def recompute_channel_prior(con: sqlite3.Connection, channel_id: str, sample_k: int = 100) -> None:
    cur = con.cursor()
    rows = cur.execute(
        """
        select vc.primary_label, vc.confidence
        from video_categories vc join rss_videos v on v.video_id=vc.video_id
        where v.channel_id=? and vc.primary_label is not null
        order by vc.updated_at desc limit ?
        """,
        (channel_id, sample_k),
    ).fetchall()
    if not rows:
        return
    cnt = Counter()
    total_w = 0.0
    for r in rows:
        lab = r[0]
        conf = float(r[1] or 0.0)
        w = max(0.5, min(3.0, 1.0 + conf))  # confidenceを重みに反映
        cnt[lab] += w
        total_w += w
    if total_w <= 0:
        return
    ratios = {k: (v / total_w) for k, v in cnt.items()}
    primary = max(ratios.items(), key=lambda x: x[1])[0]
    # 2位との差
    sorted_r = sorted(ratios.items(), key=lambda x: x[1], reverse=True)
    conf = float(sorted_r[0][1] - (sorted_r[1][1] if len(sorted_r) > 1 else 0.0))
    cur.execute(
        """
        insert into channel_category_prior(channel_id, primary_label, labels_json, confidence, sample_size, updated_at)
        values(?,?,?,?,?,?)
        on conflict(channel_id) do update set
          primary_label=excluded.primary_label,
          labels_json=excluded.labels_json,
          confidence=excluded.confidence,
          sample_size=excluded.sample_size,
          updated_at=excluded.updated_at
        """,
        (
            channel_id,
            primary,
            json.dumps(ratios, ensure_ascii=False),
            conf,
            len(rows),
            utcnow_iso(),
        ),
    )
    con.commit()


def run_once(db_path: str, rules_path: str, since_hours: int, limit: int, trending_top: int = 0) -> int:
    rules = Rules.load(rules_path)
    con = open_db(db_path)
    ensure_tables(con)
    if int(trending_top) > 0:
        rows = fetch_trending_top(con, int(trending_top))
    else:
        rows = fetch_recent_videos(con, since_hours, limit)
    done = 0
    touched_channels: set[str] = set()
    for r in rows:
        vid = r["video_id"]
        ch = r["channel_id"]
        title = normalize_text(r["title"]) or ""
        tags = parse_tags(r["keywords_json"]) or []
        desc = normalize_text(r["description_snip"]) or ""
        primary, secondary, conf, matched = decide_category(rules, con, title, tags, desc, ch)
        if primary:
            upsert_video_category(con, vid, primary, secondary, conf, matched)
            touched_channels.add(ch)
            done += 1
    # recompute prior for touched channels (cheap)
    for ch in touched_channels:
        if ch:
            recompute_channel_prior(con, ch)
    return done


def build_arg_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Rule+prior based video categorizer")
    ap.add_argument("--db", default="data/rss_watch.sqlite")
    ap.add_argument("--rules", default="config/categories.yml")
    ap.add_argument("--since-hours", type=int, default=6)
    ap.add_argument("--limit", type=int, default=5000)
    ap.add_argument("--trending-top", type=int, default=0, help="categorize top-N of trending_ranks (0=disabled)")
    return ap


def main(argv: Optional[List[str]] = None) -> int:
    ap = build_arg_parser()
    args = ap.parse_args(argv)
    n = run_once(args.db, args.rules, args.since_hours, args.limit, getattr(args, "trending_top", 0))
    print(f"categorized videos: {n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
