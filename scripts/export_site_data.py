import os
import sys
import json
import sqlite3
from pathlib import Path
from urllib.parse import urlparse


DEFAULT_DB = "index/maple_grab.db"
OUT_DIR = Path("mentomo/public/history")


KEYWORDS = [
    "姫","金融","武器庫","河童","提灯","卵","骨","ゴレ森","D子",
    "ジャクム","ビシャス","ホーンテイル","ルディ","オルビス","ヘネシス",
    "斬り賊","ナイトロード","ボウマスター","ダークナイト","プリースト","ビショップ",
    "TT","SE","HS","HB","黒字","赤字","時給","相場","露店","強化",
]


def ensure_out_dirs():
    (OUT_DIR / "by_year").mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "by_keyword").mkdir(parents=True, exist_ok=True)


def make_wayback(url: str, ts: str) -> str:
    return f"https://web.archive.org/web/{ts}/{url}" if ts else url


def slug(s: str) -> str:
    # simple filesystem-friendly slug
    return (s.replace("/", "-").replace(" ", "_").replace("#", "sharp").replace("%", "pct"))


def load_rows(db_path: str):
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    rows = list(cur.execute("SELECT url, title, wayback_timestamp FROM pages"))
    con.close()
    return rows


def main():
    db = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_DB
    ensure_out_dirs()

    rows = load_rows(db)
    items = []
    years = {}
    kw_counts = {k: 0 for k in KEYWORDS}

    for url, title, ts in rows:
        year = (ts or "")[:4]
        host = urlparse(url).netloc
        wb = make_wayback(url, ts or "")
        item = {
            "url": url,
            "title": title,
            "timestamp": ts,
            "year": year,
            "host": host,
            "wayback": wb,
        }
        items.append(item)
        if year:
            years.setdefault(year, 0)
            years[year] += 1
        blob = (title or "")
        for k in KEYWORDS:
            if (k.isascii() and k.lower() in blob.lower()) or (not k.isascii() and k in blob):
                kw_counts[k] += 1

    # Write all items
    (OUT_DIR / "items.json").write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")

    # Write years index and by_year
    years_list = sorted([{ "year": y, "count": c } for y, c in years.items()], key=lambda x: x["year"])
    (OUT_DIR / "years.json").write_text(json.dumps(years_list, ensure_ascii=False, indent=2), encoding="utf-8")
    by_year = {}
    for it in items:
        y = it.get("year")
        if not y:
            continue
        by_year.setdefault(y, []).append(it)
    for y, arr in by_year.items():
        (OUT_DIR / "by_year" / f"{y}.json").write_text(json.dumps(arr, ensure_ascii=False, indent=2), encoding="utf-8")

    # Keywords
    kws = [{"keyword": k, "count": kw_counts.get(k, 0), "slug": slug(k)} for k in KEYWORDS]
    (OUT_DIR / "keywords.json").write_text(json.dumps(kws, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Exported {len(items)} items from {db} to {OUT_DIR}")


if __name__ == "__main__":
    main()

