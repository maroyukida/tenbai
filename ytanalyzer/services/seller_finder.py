# -*- coding: utf-8 -*-
from __future__ import annotations

import csv
import random
import re
import time
import urllib.parse
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup


UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


# Typical phrases often seen in overseas-shipped or AE-like listings
PHRASE_PATTERNS = [
    r"海外倉庫",
    r"海外発送",
    r"海外直送|取り寄せ",
    r"営業日",
    r"通関",
    r"7[〜~\-－ー]?20日",
    r"10[〜~\-－ー]?30日",
    r"10[〜~\-－ー]?30営業日",
    r"未塗装",
    r"未組立|未組み|未組立て",
    r"レジン",
    r"Resin",
    r"フィギュア|figure",
    r"1/3[245]",
    r"for\s+iPhone",
    r"Universal",
    r"TPE",
    r"PU\s*レザー",
    r"BDSM",
    r"インフレータブル",
    r"バイブ|アダルト|ペニス|アナル",
]
PHRASE_RE = re.compile("|".join(PHRASE_PATTERNS), re.IGNORECASE)

OVERSEAS_WORDS = [
    "海外",
    "中国", "中華", "香港", "台湾", "韓国", "韓",
    "米国", "アメリカ", "USA", "US",
    "欧州", "EU",
    "ロシア", "ロシア連邦",
    "シンガポール", "マレーシア", "タイ", "ベトナム", "インド",
    "ドイツ", "フランス",
]
OVERSEAS_RE = re.compile("|".join(map(re.escape, OVERSEAS_WORDS)), re.IGNORECASE)


@dataclass
class ItemInfo:
    url: str
    title: str = ""
    seller_id: Optional[str] = None
    shipping_origin: Optional[str] = None
    leadtime_text: Optional[str] = None
    is_overseas: bool = False


@dataclass
class SellerStats:
    seller_id: str
    seller_url: str
    items: List[ItemInfo] = field(default_factory=list)
    title_hits: int = 0
    overseas_hits: int = 0

    def add_item(self, item: ItemInfo):
        self.items.append(item)
        if item.title and PHRASE_RE.search(item.title):
            self.title_hits += 1
        if item.is_overseas:
            self.overseas_hits += 1

    @property
    def n_items(self) -> int:
        return len(self.items)

    @property
    def hit_rate(self) -> float:
        return (self.title_hits / max(1, self.n_items)) if self.n_items else 0.0

    @property
    def overseas_rate(self) -> float:
        return (self.overseas_hits / max(1, self.n_items)) if self.n_items else 0.0

    @property
    def score(self) -> float:
        # Heuristic: prioritize overseas-rate, then title hit-rate, then sample size
        o = self.overseas_rate
        t = self.hit_rate
        size_boost = min(1.0, self.n_items / 20.0)
        return min(1.0, 0.5 * o + 0.3 * t + 0.2 * size_boost)


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Accept-Language": "ja,en;q=0.8"})
    return s


def _get(s: requests.Session, url: str, timeout: float = 20.0) -> requests.Response:
    r = s.get(url, timeout=timeout)
    r.raise_for_status()
    return r


def extract_text(el) -> str:
    return re.sub(r"\s+", " ", el.get_text(" ", strip=True)) if el else ""


def find_item_links(html: str) -> List[str]:
    soup = BeautifulSoup(html, "lxml")
    urls: List[str] = []
    for a in soup.select("a[href*='/auction/']"):
        href = a.get("href") or ""
        if not href:
            continue
        if href.startswith("/"):
            href = "https://auctions.yahoo.co.jp" + href
        if "/auction/" in href and href not in urls:
            urls.append(href)
    return urls


def parse_item_page(url: str, html: str) -> ItemInfo:
    soup = BeautifulSoup(html, "lxml")
    title = ""
    og = soup.select_one('meta[property="og:title"]')
    if og and og.get("content"):
        title = og["content"].strip()
    if not title and soup.title:
        title = soup.title.get_text(strip=True)

    seller_id = None
    for a in soup.select("a[href*='auctions.yahoo.co.jp/seller/']"):
        href = a.get("href") or ""
        m = re.search(r"seller/([^/?#]+)", href)
        if m:
            seller_id = m.group(1)
            break

    # shipping origin and leadtime detection (heuristic)
    shipping_origin = None
    leadtime_text = None
    # Try definition lists
    for dt in soup.find_all(["dt", "th"]):
        t = extract_text(dt)
        if not t:
            continue
        if ("発送" in t) or ("発送元" in t) or ("発送元の地域" in t) or ("配送" in t):
            # next dd/td
            dd = dt.find_next_sibling(["dd", "td"]) or dt.parent.find_next_sibling(["dd", "td"]) if dt.parent else None
            if dd:
                shipping_origin = extract_text(dd)
        if ("発送まで" in t) or ("納期" in t) or ("到着" in t):
            dd = dt.find_next_sibling(["dd", "td"]) or dt.parent.find_next_sibling(["dd", "td"]) if dt.parent else None
            if dd and not leadtime_text:
                leadtime_text = extract_text(dd)
    # Fallback: scan page text snippets
    if not shipping_origin:
        for el in soup.find_all(True):
            txt = extract_text(el)
            if ("発送" in txt) or ("配送" in txt):
                m = re.search(r"発送[先元]?[：: ]*([^\s\|]+)", txt)
                if m:
                    shipping_origin = m.group(1)
                    break
    # Determine overseas
    overseas = False
    if shipping_origin and OVERSEAS_RE.search(shipping_origin):
        overseas = True
    # leadtime clues
    if not overseas:
        if leadtime_text and re.search(r"(海外|通関|7[〜~\-－ー]?20日|10[〜~\-－ー]?30日|営業日)", leadtime_text):
            overseas = True
    # general page clues
    if not overseas:
        bodytxt = extract_text(soup.body) if soup.body else ""
        if re.search(r"(海外倉庫|海外発送|海外直送|通関)", bodytxt):
            overseas = True

    return ItemInfo(url=url, title=title, seller_id=seller_id, shipping_origin=shipping_origin, leadtime_text=leadtime_text, is_overseas=overseas)


def seller_url_from_id(sid: str) -> str:
    return f"https://auctions.yahoo.co.jp/seller/{sid}?user_type=c"


def build_search_url(keyword: str, start: int = 1, per_page: int = 50) -> str:
    q = urllib.parse.quote(keyword)
    # n= per page, b= start index (1-based)
    return f"https://auctions.yahoo.co.jp/search/search?p={q}&n={per_page}&b={start}&tab_ex=commerce&exflg=1"


def discover_sellers(
    seed_urls: Iterable[str] = (),
    keywords: Iterable[str] = (),
    pages_per_keyword: int = 1,
    per_page: int = 50,
    sample_items_per_seller: int = 5,
    total_item_cap: int = 500,
    delay_range: Tuple[float, float] = (1.0, 2.2),
) -> Dict[str, SellerStats]:
    s = _session()
    stats: Dict[str, SellerStats] = {}

    def handle_item_url(u: str):
        nonlocal total_fetched
        if total_fetched >= total_item_cap:
            return
        try:
            r = _get(s, u)
            info = parse_item_page(u, r.text)
            if info.seller_id:
                st = stats.get(info.seller_id)
                if not st:
                    st = SellerStats(seller_id=info.seller_id, seller_url=seller_url_from_id(info.seller_id))
                    stats[info.seller_id] = st
                if st.n_items < sample_items_per_seller:
                    st.add_item(info)
            total_fetched += 1
        except Exception:
            pass
        time.sleep(random.uniform(*delay_range))

    total_fetched = 0

    # From seed URLs (category/search/item pages)
    for u in seed_urls:
        if total_fetched >= total_item_cap:
            break
        try:
            r = _get(s, u)
            item_urls = find_item_links(r.text)
            if not item_urls:
                # If it is an item page URL, try parse directly
                handle_item_url(u)
            else:
                random.shuffle(item_urls)
                for iu in item_urls[: min(100, len(item_urls))]:
                    handle_item_url(iu)
        except Exception:
            pass
        time.sleep(random.uniform(*delay_range))

    # From keyword search
    for kw in keywords:
        if total_fetched >= total_item_cap:
            break
        for p in range(pages_per_keyword):
            if total_fetched >= total_item_cap:
                break
            start = 1 + p * per_page
            url = build_search_url(kw, start=start, per_page=per_page)
            try:
                r = _get(s, url)
                item_urls = find_item_links(r.text)
                random.shuffle(item_urls)
                for iu in item_urls[: min(100, len(item_urls))]:
                    handle_item_url(iu)
            except Exception:
                pass
            time.sleep(random.uniform(*delay_range))

    return stats


def write_sellers_csv(
    stats: Dict[str, SellerStats],
    out_csv: str,
    top_k: int = 200,
    min_items: int = 2,
    min_hit_rate: float = 0.2,
    min_overseas_rate: float = 0.0,
    min_overseas: int = 0,
) -> int:
    sellers = list(stats.values())
    sellers.sort(key=lambda s: (s.score, s.overseas_rate, s.hit_rate, s.n_items), reverse=True)
    rows = []
    for s in sellers:
        if s.n_items < min_items:
            continue
        if s.hit_rate < min_hit_rate:
            continue
        if min_overseas_rate and s.overseas_rate < min_overseas_rate:
            continue
        if min_overseas and s.overseas_hits < min_overseas:
            continue
        ex_url = s.items[0].url if s.items else ""
        ex_title = s.items[0].title if s.items else ""
        rows.append(
            {
                "seller_id": s.seller_id,
                "seller_url": s.seller_url,
                "n_items_sample": s.n_items,
                "title_hits": s.title_hits,
                "hit_rate": round(s.hit_rate, 3),
                "overseas_hits": s.overseas_hits,
                "overseas_rate": round(s.overseas_rate, 3),
                "score": round(s.score, 3),
                "example_item_url": ex_url,
                "example_title": ex_title,
            }
        )
        if len(rows) >= top_k:
            break

    if not rows:
        # still write a header for convenience
        rows = [
            {
                "seller_id": "",
                "seller_url": "",
                "n_items_sample": 0,
                "title_hits": 0,
                "hit_rate": 0.0,
                "score": 0.0,
                "example_item_url": "",
                "example_title": "",
            }
        ]

    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        for r in rows:
            w.writerow(r)
    return len(rows)


def main(argv: Optional[List[str]] = None):
    import argparse

    p = argparse.ArgumentParser(
        description="Find sellers likely doing AliExpress-style resale (heuristic)"
    )
    p.add_argument("--seed-urls", help="Text file of seed URLs (search/category/item)")
    p.add_argument("--keywords", help="Text file of keywords (one per line)")
    p.add_argument("--pages-per-keyword", type=int, default=1)
    p.add_argument("--per-page", type=int, default=50)
    p.add_argument("--sample-items-per-seller", type=int, default=5)
    p.add_argument("--total-item-cap", type=int, default=400)
    p.add_argument("--out", default="exports/seller_candidates.csv")
    p.add_argument("--top-k", type=int, default=200)
    p.add_argument("--min-items", type=int, default=2)
    p.add_argument("--min-hit-rate", type=float, default=0.2)
    p.add_argument(
        "--min-overseas-rate",
        type=float,
        default=0.5,
        help="Keep sellers with >= this overseas-rate",
    )
    p.add_argument(
        "--min-overseas",
        type=int,
        default=1,
        help="Keep sellers with >= this count of overseas items",
    )
    p.add_argument("--delay-min", type=float, default=1.0)
    p.add_argument("--delay-max", type=float, default=2.2)

    args = p.parse_args(argv)

    seed_urls: List[str] = []
    if args.seed_urls:
        try:
            with open(args.seed_urls, "r", encoding="utf-8") as f:
                seed_urls = [line.strip() for line in f if line.strip()]
        except FileNotFoundError:
            seed_urls = []

    keywords: List[str] = []
    if args.keywords:
        try:
            with open(args.keywords, "r", encoding="utf-8") as f:
                keywords = [line.strip() for line in f if line.strip()]
        except FileNotFoundError:
            keywords = []

    stats = discover_sellers(
        seed_urls=seed_urls,
        keywords=keywords,
        pages_per_keyword=args.pages_per_keyword,
        per_page=args.per_page,
        sample_items_per_seller=args.sample_items_per_seller,
        total_item_cap=args.total_item_cap,
        delay_range=(args.delay_min, args.delay_max),
    )

    n = write_sellers_csv(
        stats,
        out_csv=args.out,
        top_k=args.top_k,
        min_items=args.min_items,
        min_hit_rate=args.min_hit_rate,
        min_overseas_rate=args.min_overseas_rate,
        min_overseas=args.min_overseas,
    )
    print(f"Wrote: {args.out} (rows={n}, sellers_total={len(stats)})")


if __name__ == "__main__":
    main()





