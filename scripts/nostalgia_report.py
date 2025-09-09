import sys
import sqlite3
from urllib.parse import urlparse
from collections import Counter, defaultdict
from pathlib import Path


def main():
    db = sys.argv[1] if len(sys.argv) > 1 else "index/maple_search.db"
    out_path = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("exports/nostalgia_report.txt")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    con = sqlite3.connect(db)
    cur = con.cursor()

    rows = list(cur.execute("SELECT url, title, wayback_timestamp, text FROM pages"))
    total = len(rows)
    by_year = Counter()
    by_host = Counter()

    keywords = [
        "姫","金融","武器庫","河童","提灯","卵","骨","ゴレ森","D子",
        "ジャクム","ビシャス","ホーンテイル","ルディ","オルビス","ヘネシス",
        "斬り賊","ナイトロード","ボウマスター","ダークナイト","プリースト","ビショップ",
        "TT","SE","HS","HB","黒字","赤字","時給","相場","露店","強化",
    ]
    kw_counts = Counter()

    for url, title, ts, text in rows:
        year = (ts or "")[:4]
        if year:
            by_year[year] += 1
        host = urlparse(url).netloc
        by_host[host] += 1
        blob = (title or "") + "\n" + (text or "")
        low = blob.lower()
        for k in keywords:
            if k.isascii():
                if k.lower() in low:
                    kw_counts[k] += 1
            else:
                if k in blob:
                    kw_counts[k] += 1

    top_hosts = by_host.most_common(10)
    top_years = sorted(by_year.items())
    top_kws = kw_counts.most_common(15)

    with out_path.open("w", encoding="utf-8") as f:
        f.write(f"DB: {db}\n")
        f.write(f"Total pages: {total}\n\n")
        f.write("By Year:\n")
        for y, c in top_years:
            f.write(f"  {y}: {c}\n")
        f.write("\nTop Hosts:\n")
        for h, c in top_hosts:
            f.write(f"  {h}: {c}\n")
        f.write("\nKeyword Hits:\n")
        for k, c in top_kws:
            f.write(f"  {k}: {c}\n")

    con.close()
    print("Wrote", out_path)


if __name__ == "__main__":
    main()

