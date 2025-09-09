import sys
import sqlite3
from pathlib import Path


def make_wayback(url: str, ts: str) -> str:
    if not ts:
        return url
    return f"https://web.archive.org/web/{ts}/{url}"


def main():
    db = sys.argv[1] if len(sys.argv) > 1 else "index/maple_search.db"
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("exports/nostalgia_playlist.md")
    year_from = int(sys.argv[3]) if len(sys.argv) > 3 else 2005
    year_to = int(sys.argv[4]) if len(sys.argv) > 4 else 2009
    per_year = int(sys.argv[5]) if len(sys.argv) > 5 else 8

    keywords = ["姫","骨","ジャクム","ビシャス","斬り賊","ナイトロード","SE","TT","HS","HB","河童","提灯","武器庫","相場","強化"]

    out.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db)
    cur = con.cursor()

    lines = [f"# Nostalgia Playlist ({year_from}-{year_to})\n", f"Source: {db}\n\n"]
    seen = set()
    for y in range(year_from, year_to + 1):
        lines.append(f"## {y}\n")
        added = 0
        for kw in keywords:
            if added >= per_year:
                break
            like = f"%{kw}%"
            sql = (
                "SELECT url, title, wayback_timestamp FROM pages "
                "WHERE substr(wayback_timestamp,1,4)=? AND (title LIKE ? OR text LIKE ?) "
                "LIMIT 20"
            )
            for url, title, ts in cur.execute(sql, (str(y), like, like)):
                key = (url, ts)
                if key in seen:
                    continue
                seen.add(key)
                wb = make_wayback(url, ts)
                title_disp = title if title else url
                lines.append(f"- {title_disp}\n  - {wb}\n")
                added += 1
                if added >= per_year:
                    break
        if added == 0:
            lines.append("- (no items)\n")
        lines.append("\n")

    with out.open("w", encoding="utf-8") as f:
        f.writelines(line + ("" if line.endswith("\n") else "\n") for line in lines)
    con.close()
    print("Wrote", out)


if __name__ == "__main__":
    main()

