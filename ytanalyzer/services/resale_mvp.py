# -*- coding: utf-8 -*-
from __future__ import annotations

import csv
import re
import time
import random
import math
from dataclasses import dataclass
from typing import Iterable, List, Optional, Tuple

import requests
import json
from bs4 import BeautifulSoup
from ..config import Config

# Optional libraries for AE-keyless fallback search
try:
    import cloudscraper  # type: ignore
except Exception:  # pragma: no cover
    cloudscraper = None  # type: ignore

# Prefer new 'ddgs' package; fall back to old 'duckduckgo_search'
DDGS = None  # type: ignore
try:  # pragma: no cover
    from ddgs import DDGS as _DDGS  # type: ignore
    DDGS = _DDGS
except Exception:
    try:
        from duckduckgo_search import DDGS as _DDGS  # type: ignore
        DDGS = _DDGS
    except Exception:
        DDGS = None  # type: ignore

try:
    from PIL import Image  # type: ignore
    import imagehash  # type: ignore
    _IMG_OK = True
except Exception:
    _IMG_OK = False


UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


@dataclass
class YahooItem:
    url: str
    title: str = ""
    price: Optional[float] = None
    image: Optional[str] = None
    seller_id: Optional[str] = None


@dataclass
class AliItem:
    product_id: str
    url: str
    title: str
    price: Optional[float]
    image: Optional[str]


def _get(session: requests.Session, url: str, timeout: float = 20.0) -> requests.Response:
    resp = session.get(url, timeout=timeout)
    resp.raise_for_status()
    return resp


def extract_text(el) -> str:
    return re.sub(r"\s+", " ", el.get_text(" ", strip=True)) if el else ""


def parse_price_num(text: str) -> Optional[float]:
    m = re.search(r"([0-9][0-9,]*)", text or "")
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", ""))
    except Exception:
        return None


def parse_yahoo_item_html(url: str, html: str) -> YahooItem:
    soup = BeautifulSoup(html, "lxml")
    title = ""
    image = None
    price = None
    seller_id = None

    # Try OpenGraph
    ogt = soup.select_one('meta[property="og:title"]')
    if ogt and ogt.get("content"):
        title = ogt["content"].strip()
    if not title and soup.title:
        title = soup.title.get_text(strip=True)

    ogi = soup.select_one('meta[property="og:image"]')
    if ogi and ogi.get("content"):
        image = ogi["content"].strip()

    # Price candidates
    meta_price = soup.select_one('meta[property="product:price:amount"]')
    if meta_price and meta_price.get("content"):
        price = parse_price_num(meta_price["content"]) or price

    # Visible price hints (imperfect, heuristic)
    for sel in [
        "span.Price__value",  # common in Yahoo! pages
        "span.Price--buynow",  # hypothetical selector
        "dd.Price__value",     # another pattern
        "span.price",          # generic
    ]:
        el = soup.select_one(sel)
        if el:
            p = parse_price_num(extract_text(el))
            if p:
                price = p
                break

    # Seller id hint (from profile anchors)
    for a in soup.select("a[href*='auctions.yahoo.co.jp/seller/']"):
        href = a.get("href") or ""
        m = re.search(r"seller/([^/?#]+)", href)
        if m:
            seller_id = m.group(1)
            break

    return YahooItem(url=url, title=title, price=price, image=image, seller_id=seller_id)


def fetch_yahoo_item(url: str, delay_range: Tuple[float, float] = (1.2, 2.2)) -> YahooItem:
    session = requests.Session()
    session.headers.update({"User-Agent": UA, "Accept-Language": "ja,en;q=0.8"})
    r = _get(session, url)
    time.sleep(random.uniform(*delay_range))
    return parse_yahoo_item_html(url, r.text)


def crawl_seller_items(seller_url: str, max_pages: int = 1, delay_range: Tuple[float, float] = (1.5, 2.8)) -> List[str]:
    """Extract item detail URLs from a seller listing page (heuristic, 1-3 pages).

    Note: This relies on public HTML; adjust selectors as needed.
    """
    session = requests.Session()
    session.headers.update({"User-Agent": UA, "Accept-Language": "ja,en;q=0.8"})

    urls: List[str] = []
    page_url = seller_url
    for _ in range(max_pages):
        r = _get(session, page_url)
        soup = BeautifulSoup(r.text, "lxml")
        for a in soup.select("a[href*='/auction/']"):
            href = a.get("href") or ""
            # Normalize absolute URL if needed
            if href.startswith("/"):
                href = f"https://auctions.yahoo.co.jp{href}"
            if "/auction/" in href and href not in urls:
                urls.append(href)

        # pager: find a "next" anchor by rel/aria-label or visible text
        next_a = None
        for sel in ["a[rel='next']", "a[aria-label='次へ']"]:
            next_a = soup.select_one(sel)
            if next_a:
                break
        if not next_a:
            for a in soup.select("a"):
                if ('次へ' in extract_text(a)) or ('次のページ' in extract_text(a)):
                    next_a = a
                    break
        if not next_a:
            break
        href = next_a.get("href") or ""
        if href.startswith("/"):
            href = f"https://auctions.yahoo.co.jp{href}"
        page_url = href
        time.sleep(random.uniform(*delay_range))
    return urls


class AliExpressAdapter:
    """AliExpress search via official API (optional).

    Requires environment variables:
      - ALIEXPRESS_APP_KEY
      - ALIEXPRESS_APP_SECRET
      - ALIEXPRESS_TRACKING_ID

    Falls back to no results if keys or library are absent.
    """

    def __init__(self, app_key: Optional[str], app_secret: Optional[str], tracking_id: Optional[str]):
        self.app_key = app_key
        self.app_secret = app_secret
        self.tracking_id = tracking_id
        self._api = None
        self._init_api()

    def _init_api(self):
        if not (self.app_key and self.app_secret and self.tracking_id):
            return
        try:
            # Lazy import to avoid hard dependency
            from aliexpress_api import AliexpressApi  # type: ignore
            self._api = AliexpressApi(app_key=self.app_key, app_secret=self.app_secret, tracking_id=self.tracking_id)
        except Exception:
            self._api = None

    def search(self, query: str, limit: int = 3) -> List[AliItem]:
        if not self._api:
            # Fallback: AE-keyless search via DuckDuckGo + HTML parsing
            try:
                return self._search_web(query=query, limit=limit)
            except Exception:
                return []
        try:
            res = self._api.search_products(keywords=query, page_no=1, page_size=max(1, min(10, limit)))
            items = []
            for p in (res or {}).get("products", [])[:limit]:
                items.append(
                    AliItem(
                        product_id=str(p.get("productId")),
                        url=p.get("productUrl") or "",
                        title=p.get("productTitle") or "",
                        price=_parse_ae_price(p.get("targetSalePrice")),
                        image=p.get("imageUrl") or None,
                    )
                )
            return items
        except Exception:
            return []

    # ---------- AE-keyless fallback helpers ----------
    def _search_web(self, query: str, limit: int = 3) -> List[AliItem]:
        """Search AliExpress without official API.

        Approach: DuckDuckGo site search -> filter '/item/<id>.html' -> fetch with
        cloudscraper/requests -> parse title/image/price (best-effort).
        """
        q = re.sub(r"\s+", " ", (query or "")).strip()
        if not q:
            return []
        # Build a few query variants to improve hit rate on AE
        variants = self._build_query_variants(q)

        cand_urls: List[str] = []
        try:
            if DDGS is None:
                raise RuntimeError("duckduckgo-search not available")
            with DDGS() as ddgs:  # type: ignore
                for v in variants:
                    search_q = f"site:aliexpress.com {v}"
                    for r in ddgs.text(search_q, region="wt-wt", safesearch="Off", max_results=max(10, limit * 3)):
                        href = (r or {}).get("href") or (r or {}).get("link") or ""
                        if not isinstance(href, str):
                            continue
                        href = self._normalize_ae_url(href)
                        if self._is_item_url(href) and href not in cand_urls:
                            cand_urls.append(href)
                        if len(cand_urls) >= limit * 3:
                            break
                    if len(cand_urls) >= limit * 3:
                        break
        except Exception:
            return []

        items: List[AliItem] = []
        for u in cand_urls[: max(1, limit)]:
            try:
                html = self._fetch_html(u)
                if not html:
                    continue
                ai = self._parse_ae_item_html(u, html)
                if ai:
                    items.append(ai)
            except Exception:
                continue
        return items[:limit]

    def _build_query_variants(self, title: str) -> List[str]:
        # Remove Yahoo suffix
        t = title.split(" - Yahoo!")[0]
        # Keep scale like 1/7, 1/35
        m_scale = re.findall(r"\b1\/(\d{1,3})\b", t)
        scale = ("1/" + m_scale[0]) if m_scale else ""
        # Basic replacements JA->EN tokens
        rep = [
            (r"未塗装|未組立|未組み|未組立て", "unpainted unassembled"),
            (r"ガレージキット|ガレキ", "garage kit"),
            (r"レジン", "resin"),
            (r"フィギュア|スタチュー|figure", "figure"),
            (r"模型|プラモデル|モデル", "model kit"),
            (r"水着", "swimsuit"),
            (r"ケース|カバー", "case"),
            (r"スマホ|携帯", "phone"),
            (r"PUレザー", "PU leather"),
            (r"レザー", "leather"),
            (r"アニメ|マンガ", "anime manga"),
        ]
        base = t
        for pat, repl in rep:
            base = re.sub(pat, repl, base)
        # Keep latin letters/numbers and a few JA tokens turned EN
        words = re.findall(r"[A-Za-z0-9/\-]+", base)
        core = " ".join(words)
        # Variants from generic patterns
        variants = []
        if scale:
            variants.append(f"{scale} resin kit figure {core}")
        variants.append(f"resin kit figure {core}")
        variants.append(f"resin figure {core}")
        variants.append(core)
        # Deduplicate and shorten
        uniq: List[str] = []
        for v in variants:
            vv = re.sub(r"\s+", " ", v).strip()
            if vv and vv not in uniq:
                uniq.append(vv)
        return uniq[:4]

    def _fetch_html(self, url: str, timeout: float = 20.0) -> Optional[str]:
        headers = {"User-Agent": UA, "Accept-Language": "en,ja;q=0.8"}
        # Prefer cloudscraper if available
        try:
            if cloudscraper is not None:  # type: ignore
                s = cloudscraper.create_scraper()  # type: ignore
                r = s.get(url, headers=headers, timeout=timeout)
                if r.status_code == 200 and r.text:
                    return r.text
        except Exception:
            pass
        try:
            r = requests.get(url, headers=headers, timeout=timeout)
            if r.status_code == 200 and r.text:
                return r.text
        except Exception:
            pass
        return None

    def _is_item_url(self, url: str) -> bool:
        try:
            return bool(re.search(r"aliexpress\.[a-z.]+/(item|i|p)/\d+\.html", url))
        except Exception:
            return False

    def _normalize_ae_url(self, url: str) -> str:
        try:
            m = re.search(r"(https?://[^/]+/item/\d+\.html)", url)
            if m:
                core = m.group(1)
                core = re.sub(r"https?://[^/]+", "https://www.aliexpress.com", core)
                return core
        except Exception:
            pass
        return url

    def _parse_ae_item_html(self, url: str, html: str) -> Optional[AliItem]:
        # Title from OG or H1
        title = ""
        m = re.search(r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']', html, re.IGNORECASE)
        if m:
            title = m.group(1).strip()
        if not title:
            m = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.IGNORECASE | re.DOTALL)
            if m:
                title = re.sub(r"<[^>]+>", " ", m.group(1)).strip()

        # Image from OG
        image = None
        mi = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', html, re.IGNORECASE)
        if mi:
            image = mi.group(1).strip()

        # Price (heuristic)
        price: Optional[float] = None
        # Try JSON-LD offers first (safer currency info)
        try:
            for jm in re.finditer(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', html, re.IGNORECASE | re.DOTALL):
                js = jm.group(1).strip()
                # Attempt to parse; tolerate surrounding whitespace and arrays
                candidates = []
                try:
                    obj = json.loads(js)
                    candidates = obj if isinstance(obj, list) else [obj]
                except Exception:
                    # Some pages minify multiple JSON blocks; split heuristically
                    for part in re.split(r"}\s*\n?\s*\{", js):
                        s = part.strip()
                        if not s:
                            continue
                        if not s.startswith('{'):
                            s = '{' + s
                        if not s.endswith('}'):
                            s = s + '}'
                        try:
                            candidates.append(json.loads(s))
                        except Exception:
                            continue
                for obj in candidates:
                    try:
                        offers = obj.get('offers') if isinstance(obj, dict) else None
                        if isinstance(offers, dict):
                            cur = (offers.get('priceCurrency') or '').upper()
                            p = offers.get('price') if 'price' in offers else offers.get('lowPrice')
                            if p is not None:
                                v = float(str(p).replace(',', '').strip())
                                if cur in ('USD', 'US'):
                                    price = v
                                    raise StopIteration
                    except StopIteration:
                        raise
                    except Exception:
                        continue
        except StopIteration:
            pass
        except Exception:
            pass
        for pat in [
            r'formatedActivityPrice"\s*:\s*"\s*(?:US\s*\$)?\s*([0-9][0-9\.,]*)',
            r'formatedPrice"\s*:\s*"\s*(?:US\s*\$)?\s*([0-9][0-9\.,]*)',
            r'\"salePrice\"\s*:\s*\"\s*(?:US\s*\$)?\s*([0-9][0-9\.,]*)',
            r'"targetSalePrice"\s*:\s*"\s*(?:US\s*\$)?\s*([0-9][0-9\.,]*)',
            r'>\s*US\s*\$\s*([0-9][0-9\.,]*)\s*<',
            r'"salePrice"\s*:\s*\{[^}]*?"value"\s*:\s*([0-9][0-9\.,]*)',
            r'"minActivityAmount"\s*:\s*\{[^}]*?"value"\s*:\s*([0-9][0-9\.,]*)',
            r'"maxActivityAmount"\s*:\s*\{[^}]*?"value"\s*:\s*([0-9][0-9\.,]*)',
            r'"minAmount"\s*:\s*\{[^}]*?"value"\s*:\s*([0-9][0-9\.,]*)',
            r'"discountPrice"\s*:\s*\{[^}]*?"value"\s*:\s*([0-9][0-9\.,]*)',
            r'"currency"\s*:\s*"USD"[^}]*?"value"\s*:\s*([0-9][0-9\.,]*)',
        ]:
            mm = re.search(pat, html)
            if mm:
                try:
                    raw = mm.group(1).replace(",", "").strip()
                    price = float(raw)
                    break
                except Exception:
                    pass
        # guard against false tiny values from noisy matches
        if price is not None and price < 2.0:
            price = None

        pid = ""
        mp = re.search(r"/item/(\d+)\.html", url)
        if mp:
            pid = mp.group(1)

        if not title and not image:
            return None
        return AliItem(product_id=pid or url, url=url, title=title, price=price, image=image)


def _parse_ae_price(v) -> Optional[float]:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(str(v).replace(",", "").strip())
    except Exception:
        return None


def title_similarity(a: str, b: str) -> float:
    # Lightweight similarity (normalized overlap)
    aa = re.sub(r"\s+", " ", a.lower()).strip()
    bb = re.sub(r"\s+", " ", b.lower()).strip()
    if not aa or not bb:
        return 0.0
    # word-based Jaccard
    sa = set(aa.split())
    sb = set(bb.split())
    if not sa or not sb:
        return 0.0
    inter = len(sa & sb)
    union = len(sa | sb)
    return inter / union if union else 0.0


def logistic(x: float, k: float = 6.0, x0: float = 2.0) -> float:
    try:
        return 1.0 / (1.0 + math.exp(-k * (x - x0)))
    except OverflowError:
        return 0.0 if x < x0 else 1.0


def phash_distance(url1: Optional[str], url2: Optional[str], timeout: float = 20.0) -> Optional[int]:
    if not _IMG_OK or not url1 or not url2:
        return None
    try:
        r1 = requests.get(url1, timeout=timeout, headers={"User-Agent": UA})
        r1.raise_for_status()
        r2 = requests.get(url2, timeout=timeout, headers={"User-Agent": UA})
        r2.raise_for_status()
        import io

        img1 = Image.open(io.BytesIO(r1.content))
        img2 = Image.open(io.BytesIO(r2.content))
        return int(imagehash.phash(img1) - imagehash.phash(img2))
    except Exception:
        return None


def resale_score(yahoo: YahooItem, ali: AliItem, img_dist: Optional[int]) -> float:
    t = title_similarity(yahoo.title or "", ali.title or "")
    price_ratio = None
    if yahoo.price and ali.price and ali.price > 0:
        price_ratio = (yahoo.price) / ali.price
    price_feat = logistic(price_ratio) if price_ratio is not None else 0.0

    if img_dist is None:
        img_feat = 0.0
    else:
        img_feat = 1.0 if img_dist <= 6 else (0.6 if img_dist <= 12 else 0.0)

    # weights can be tuned later
    return 0.45 * img_feat + 0.30 * t + 0.20 * price_feat + 0.05


def estimate_profit(
    yahoo: YahooItem,
    ali: AliItem | None,
    cfg: Optional[Config] = None,
) -> dict:
    cfg = cfg or Config()
    # Revenue: Yahoo price + assumed shipping income
    rev = (yahoo.price or 0.0) + (cfg.yahoo_shipping_income_jpy or 0.0)
    # Cost: AE USD price * FX + assumed AE shipping + misc
    ae_price = (ali.price if ali else None)
    cost = 0.0
    if ae_price is not None and ae_price >= 0:
        cost = ae_price * (cfg.fx_usdjpy or 1.0)
    cost += (cfg.ae_shipping_jpy or 0.0) + (cfg.misc_cost_jpy or 0.0)
    # Fees: platform fee on revenue
    fee = rev * (cfg.market_fee_rate or 0.0)
    profit = rev - fee - cost
    margin = (profit / rev) if rev > 0 else None
    return {
        "est_revenue_jpy": round(rev, 2) if rev else "",
        "est_cost_jpy": round(cost, 2) if cost else "",
        "est_fee_jpy": round(fee, 2) if fee else "",
        "est_profit_jpy": round(profit, 2) if rev or cost else "",
        "est_margin_rate": round(margin, 4) if margin is not None else "",
    }


def run_mvp(
    yahoo_urls: Iterable[str],
    out_csv: str,
    ae: AliExpressAdapter,
    per_item_candidates: int = 3,
    delay_range: Tuple[float, float] = (1.2, 2.2),
) -> None:
    rows: List[dict] = []
    cfg = Config()
    for url in yahoo_urls:
        url = url.strip()
        if not url:
            continue
        try:
            yi = fetch_yahoo_item(url, delay_range=delay_range)
        except Exception as e:
            rows.append({
                "yahoo_url": url,
                "yahoo_title": "",
                "yahoo_price": "",
                "yahoo_image": "",
                "ae_url": "",
                "ae_title": "",
                "ae_price": "",
                "ae_image": "",
                "title_sim": "",
                "img_dist": "",
                "price_ratio": "",
                "score": "",
                "error": f"fetch_yahoo_failed: {e}",
            })
            continue

        candidates = ae.search(yi.title, limit=per_item_candidates) if yi.title else []
        if not candidates:
            rows.append({
                "yahoo_url": yi.url,
                "yahoo_title": yi.title,
                "yahoo_price": yi.price or "",
                "yahoo_image": yi.image or "",
                "ae_url": "",
                "ae_title": "",
                "ae_price": "",
                "ae_image": "",
                "title_sim": "",
                "img_dist": "",
                "price_ratio": "",
                "score": 0.0,
                **estimate_profit(yi, None, cfg),
                "error": "no_ae_candidates",
            })
            continue

        # Evaluate candidates and take the best
        best = None
        best_score = -1.0
        best_features = (0.0, None, None)
        for c in candidates:
            img_dist = phash_distance(yi.image, c.image)
            s = resale_score(yi, c, img_dist)
            if s > best_score:
                best_score = s
                tr = title_similarity(yi.title, c.title)
                pr = None
                if yi.price and c.price and c.price > 0:
                    pr = yi.price / c.price
                best = c
                best_features = (tr, img_dist, pr)

        if best is None:
            rows.append({
                "yahoo_url": yi.url,
                "yahoo_title": yi.title,
                "yahoo_price": yi.price or "",
                "yahoo_image": yi.image or "",
                "ae_url": "",
                "ae_title": "",
                "ae_price": "",
                "ae_image": "",
                "title_sim": "",
                "img_dist": "",
                "price_ratio": "",
                "score": 0.0,
                **estimate_profit(yi, None, cfg),
                "error": "no_best",
            })
        else:
            t_sim, img_dist, pr = best_features
            rows.append({
                "yahoo_url": yi.url,
                "yahoo_title": yi.title,
                "yahoo_price": yi.price or "",
                "yahoo_image": yi.image or "",
                "ae_url": best.url,
                "ae_title": best.title,
                "ae_price": best.price or "",
                "ae_image": best.image or "",
                "title_sim": round(t_sim, 4) if isinstance(t_sim, float) else "",
                "img_dist": img_dist if img_dist is not None else "",
                "price_ratio": round(pr, 4) if isinstance(pr, float) else "",
                "score": round(best_score, 4),
                **estimate_profit(yi, best, cfg),
                "error": "",
            })

    # write CSV
    if rows:
        fieldnames = list(rows[0].keys())
    else:
        fieldnames = [
            "yahoo_url","yahoo_title","yahoo_price","yahoo_image",
            "ae_url","ae_title","ae_price","ae_image",
            "title_sim","img_dist","price_ratio","score",
            "est_revenue_jpy","est_cost_jpy","est_fee_jpy","est_profit_jpy","est_margin_rate",
            "error"
        ]
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


def read_lines(path: str) -> List[str]:
    with open(path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def main(argv: Optional[List[str]] = None):
    import argparse
    from ..config import Config

    p = argparse.ArgumentParser(description="Yahoo x AliExpress resale MVP matcher")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--input-urls", help="Text file of Yahoo item URLs (one per line)")
    g.add_argument("--seller-url", help="Yahoo seller listing URL (crawl a few pages)")
    p.add_argument("--seller-pages", type=int, default=1, help="Pages to crawl from seller list")
    p.add_argument("--out", default="exports/resale_candidates.csv", help="Output CSV path")
    p.add_argument("--per-item-candidates", type=int, default=3)
    p.add_argument("--delay-min", type=float, default=1.2)
    p.add_argument("--delay-max", type=float, default=2.2)

    args = p.parse_args(argv)

    cfg = Config()
    ae = AliExpressAdapter(
        app_key=cfg.aliexpress_app_key,
        app_secret=cfg.aliexpress_app_secret,
        tracking_id=cfg.aliexpress_tracking_id,
    )

    if args.input_urls:
        urls = read_lines(args.input_urls)
    else:
        urls = crawl_seller_items(args.seller_url, max_pages=args.seller_pages)

    if not urls:
        print("No Yahoo URLs found. Nothing to do.")
        return

    run_mvp(
        yahoo_urls=urls,
        out_csv=args.out,
        ae=ae,
        per_item_candidates=args.per_item_candidates,
        delay_range=(args.delay_min, args.delay_max),
    )
    print(f"Wrote: {args.out} (rows={len(urls)})")

