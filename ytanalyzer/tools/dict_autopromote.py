# -*- coding: utf-8 -*-
from __future__ import annotations

"""
Dictionary auto-promotion (AIなし):
  - 直近24hの分類済み動画からカテゴリ別に有効語を抽出
  - しきい値を満たした語を config/categories.yml の includes に自動追加

安全装置:
  - 1カテゴリあたり最大10語/日、全体最大50語/日
  - precision>=0.6、出現動画数>=15、他カテゴリとの分離>=0.25
  - 既存includes/excludesに重複追加しない

Usage:
  python -m ytanalyzer.tools.dict_autopromote --db data/rss_watch.sqlite --rules config/categories.yml
"""

import argparse
import json
import re
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Tuple

import yaml


def load_rules(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def save_rules(path: str, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)


def open_db(path: str) -> sqlite3.Connection:
    con = sqlite3.connect(path, timeout=60)
    con.row_factory = sqlite3.Row
    return con


TOKEN_RE = re.compile(r"[#@]?[\w\-\u3040-\u30ff\u4e00-\u9faf]{2,30}")


def tokenize(text: str) -> List[str]:
    return [t for t in TOKEN_RE.findall(text or "") if not t.isdigit()]


def collect_terms(con: sqlite3.Connection, hours: int = 24) -> List[Tuple[str, str]]:
    cur = con.cursor()
    rows = cur.execute(
        """
        select v.title, v.keywords_json, vc.primary_label as cat
        from video_categories vc join rss_videos v on v.video_id=vc.video_id
        where vc.primary_label is not null
          and strftime('%s', replace(substr(coalesce(vc.updated_at,''),1,19),'T',' '))>=strftime('%s','now', ?)
        """,
        (f"-{hours} hours",),
    ).fetchall()
    out: List[Tuple[str, str]] = []
    for r in rows:
        title = r[0] or ""
        try:
            tags = json.loads(r[1] or "[]")
        except Exception:
            tags = []
        text = title + " " + " ".join([str(t) for t in tags if t])
        for tok in tokenize(text):
            out.append((r[2], tok))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Auto promote category terms from recent videos")
    ap.add_argument("--db", default="data/rss_watch.sqlite")
    ap.add_argument("--rules", default="config/categories.yml")
    ap.add_argument("--hours", type=int, default=24)
    ap.add_argument("--per-cat", type=int, default=10)
    ap.add_argument("--total", type=int, default=50)
    ap.add_argument("--min-count", type=int, default=15)
    ap.add_argument("--min-prec", type=float, default=0.6)
    ap.add_argument("--min-margin", type=float, default=0.25)
    args = ap.parse_args()

    rules = load_rules(args.rules)
    cats = rules.get("categories", [])
    existing = {c["name"]: set(c.get("includes", [])) for c in cats}
    excludes_global = [re.compile(p, re.I) for p in rules.get("excludes_global", [])]

    con = open_db(args.db)
    pairs = collect_terms(con, args.hours)
    if not pairs:
        print("no recent labeled videos; skip")
        return 0
    # counts
    by_cat: Dict[str, Counter] = defaultdict(Counter)
    total: Counter = Counter()
    for cat, tok in pairs:
        total[tok] += 1
        by_cat[cat][tok] += 1

    proposals: Dict[str, List[Tuple[str, float, int, float]]] = defaultdict(list)
    for c in cats:
        name = c["name"]
        cnt = by_cat.get(name, Counter())
        for tok, n in cnt.items():
            if n < args.min_count:
                continue
            # global excludes
            if any(rx.search(tok) for rx in excludes_global):
                continue
            prec = n / max(1, total[tok])  # precision
            # margin: vs best other category share
            best_other = 0.0
            for oc, ocnt in by_cat.items():
                if oc == name:
                    continue
                best_other = max(best_other, ocnt.get(tok, 0) / max(1, total[tok]))
            margin = prec - best_other
            if prec >= args.min_prec and margin >= args.min_margin:
                score = n * prec
                proposals[name].append((tok, score, n, prec))

    added_total = 0
    for c in cats:
        name = c["name"]
        inc = set(c.get("includes", []))
        prop = sorted(proposals.get(name, []), key=lambda x: x[1], reverse=True)
        added = 0
        for tok, score, n, prec in prop:
            if added >= args.per_cat or added_total >= args.total:
                break
            # 既存パターンに似たものがあるか（単純包含チェック）
            if any(tok in pat for pat in inc):
                continue
            # 英数字は単語境界で、和文はそのまま
            if re.match(r"^[A-Za-z0-9_\-]+$", tok):
                pat = rf"\b{re.escape(tok)}\b"
            else:
                pat = re.escape(tok)
            c.setdefault("includes", []).append(pat)
            inc.add(pat)
            added += 1
            added_total += 1
    if added_total > 0:
        save_rules(args.rules, rules)
    print(f"auto-promoted terms: {added_total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

