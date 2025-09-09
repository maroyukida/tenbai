# -*- coding: utf-8 -*-
from __future__ import annotations

import csv
import random
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from .resale_mvp import (
    AliExpressAdapter,
    crawl_seller_items,
    fetch_yahoo_item,
    phash_distance,
    resale_score,
    title_similarity,
    estimate_profit,
)
from ..config import Config


@dataclass
class ItemMatch:
    yahoo_url: str
    yahoo_title: str
    yahoo_price: float | None
    yahoo_image: str | None
    ae_url: str | None
    ae_title: str | None
    ae_price: float | None
    ae_image: str | None
    title_sim: float | None
    img_dist: int | None
    price_ratio: float | None
    score: float
    est_revenue_jpy: float | None = None
    est_cost_jpy: float | None = None
    est_fee_jpy: float | None = None
    est_profit_jpy: float | None = None
    est_margin_rate: float | None = None


def verify_item(url: str, ae: AliExpressAdapter, per_item_candidates: int, delay_range: Tuple[float, float], cfg: Optional[Config] = None) -> ItemMatch | None:
    try:
        yi = fetch_yahoo_item(url, delay_range=delay_range)
    except Exception:
        return None

    candidates = ae.search(yi.title, limit=per_item_candidates) if yi.title else []
    best = None
    best_score = -1.0
    best_t = None
    best_dist = None
    best_pr = None

    for c in candidates:
        d = phash_distance(yi.image, c.image)
        s = resale_score(yi, c, d)
        if s > best_score:
            best_score = s
            best = c
            best_t = title_similarity(yi.title or "", c.title or "")
            best_dist = d
            if yi.price and c.price and c.price > 0:
                best_pr = yi.price / c.price
            else:
                best_pr = None

    if best is None:
        prof = estimate_profit(yi, None, cfg)
        return ItemMatch(
            yahoo_url=yi.url,
            yahoo_title=yi.title,
            yahoo_price=yi.price,
            yahoo_image=yi.image,
            ae_url=None,
            ae_title=None,
            ae_price=None,
            ae_image=None,
            title_sim=None,
            img_dist=None,
            price_ratio=None,
            score=0.0,
            est_revenue_jpy=prof.get("est_revenue_jpy") or None,
            est_cost_jpy=prof.get("est_cost_jpy") or None,
            est_fee_jpy=prof.get("est_fee_jpy") or None,
            est_profit_jpy=prof.get("est_profit_jpy") or None,
            est_margin_rate=prof.get("est_margin_rate") or None,
        )

    prof = estimate_profit(yi, best, cfg)
    return ItemMatch(
        yahoo_url=yi.url,
        yahoo_title=yi.title,
        yahoo_price=yi.price,
        yahoo_image=yi.image,
        ae_url=best.url,
        ae_title=best.title,
        ae_price=best.price,
        ae_image=best.image,
        title_sim=best_t,
        img_dist=best_dist,
        price_ratio=best_pr,
        score=best_score,
        est_revenue_jpy=prof.get("est_revenue_jpy") or None,
        est_cost_jpy=prof.get("est_cost_jpy") or None,
        est_fee_jpy=prof.get("est_fee_jpy") or None,
        est_profit_jpy=prof.get("est_profit_jpy") or None,
        est_margin_rate=prof.get("est_margin_rate") or None,
    )


def verify_seller(
    seller_url: str,
    ae: AliExpressAdapter,
    items_per_seller: int = 3,
    pages_per_seller: int = 1,
    per_item_candidates: int = 3,
    delay_range: Tuple[float, float] = (1.2, 2.2),
) -> List[ItemMatch]:
    urls = crawl_seller_items(seller_url, max_pages=pages_per_seller, delay_range=delay_range)
    random.shuffle(urls)
    matches: List[ItemMatch] = []
    cfg = Config()
    for u in urls[: items_per_seller]:
        m = verify_item(u, ae=ae, per_item_candidates=per_item_candidates, delay_range=delay_range, cfg=cfg)
        if m:
            matches.append(m)
    return matches


def aggregate_seller_result(matches: List[ItemMatch], score_threshold: float = 0.72) -> Dict[str, float | int | str | None]:
    if not matches:
        return {
            "items_scanned": 0,
            "with_ae_candidates": 0,
            "high_score_count": 0,
            "avg_score": 0.0,
            "max_score": 0.0,
            "example_yahoo_url": "",
            "example_ae_url": "",
        }
    scores = [m.score for m in matches]
    with_ae = sum(1 for m in matches if m.ae_url)
    high = sum(1 for m in matches if m.score >= score_threshold)
    best = max(matches, key=lambda x: x.score)
    avg = sum(scores) / max(1, len(scores))
    profits = [m.est_profit_jpy for m in matches if isinstance(m.est_profit_jpy, (int, float))]
    avg_profit = (sum(profits) / len(profits)) if profits else 0.0
    margins = [m.est_margin_rate for m in matches if isinstance(m.est_margin_rate, (int, float))]
    avg_margin = (sum(margins) / len(margins)) if margins else 0.0
    return {
        "items_scanned": len(matches),
        "with_ae_candidates": with_ae,
        "high_score_count": high,
        "avg_score": round(avg, 4),
        "max_score": round(best.score, 4),
        "avg_profit_jpy": round(avg_profit, 2),
        "avg_margin_rate": round(avg_margin, 4),
        "example_yahoo_url": best.yahoo_url,
        "example_ae_url": best.ae_url or "",
    }


def read_seller_candidates(path: str) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    with open(path, "r", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            rows.append(row)
    # sort by score desc if present
    def _score(row):
        try:
            return float(row.get("score", 0) or 0)
        except Exception:
            return 0.0
    rows.sort(key=_score, reverse=True)
    return rows


def write_verified_csv(records: List[Dict[str, str | int | float]], out_path: str) -> None:
    if not records:
        fields = [
            "seller_id","seller_url","items_scanned","with_ae_candidates","high_score_count",
            "avg_score","max_score","avg_profit_jpy","avg_margin_rate","example_yahoo_url","example_ae_url",
        ]
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=fields).writeheader()
        return

    fields = list(records[0].keys())
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for rec in records:
            w.writerow(rec)


def write_item_details(matches_by_seller: Dict[str, List[ItemMatch]], out_path: str) -> None:
    rows: List[Dict[str, str | int | float]] = []
    for sid, items in matches_by_seller.items():
        for m in items:
            rows.append({
                "seller_id": sid,
                "yahoo_url": m.yahoo_url,
                "yahoo_title": m.yahoo_title,
                "yahoo_price": m.yahoo_price or "",
                "yahoo_image": m.yahoo_image or "",
                "ae_url": m.ae_url or "",
                "ae_title": m.ae_title or "",
                "ae_price": m.ae_price or "",
                "ae_image": m.ae_image or "",
                "title_sim": round(m.title_sim, 4) if isinstance(m.title_sim, float) else "",
                "img_dist": m.img_dist if m.img_dist is not None else "",
                "price_ratio": round(m.price_ratio, 4) if isinstance(m.price_ratio, float) else "",
                "score": round(m.score, 4),
                "est_revenue_jpy": m.est_revenue_jpy or "",
                "est_cost_jpy": m.est_cost_jpy or "",
                "est_fee_jpy": m.est_fee_jpy or "",
                "est_profit_jpy": m.est_profit_jpy or "",
                "est_margin_rate": m.est_margin_rate or "",
            })
    if not rows:
        fields = [
            "seller_id","yahoo_url","yahoo_title","yahoo_price","yahoo_image","ae_url","ae_title","ae_price","ae_image",
            "title_sim","img_dist","price_ratio","score","est_revenue_jpy","est_cost_jpy","est_fee_jpy","est_profit_jpy","est_margin_rate",
        ]
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=fields).writeheader()
        return
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        for r in rows:
            w.writerow(r)


def main(argv: Optional[List[str]] = None):
    import argparse

    p = argparse.ArgumentParser(description="Verify top seller candidates by sampling items and scoring AE matches")
    p.add_argument("--in", dest="inp", default="exports/seller_candidates.csv")
    p.add_argument("--out", default="exports/seller_verified.csv")
    p.add_argument("--sellers", type=int, default=10, help="Number of top sellers to verify")
    p.add_argument("--items-per-seller", type=int, default=3)
    p.add_argument("--pages-per-seller", type=int, default=1)
    p.add_argument("--per-item-candidates", type=int, default=3)
    p.add_argument("--score-threshold", type=float, default=0.72)
    # Filters to keep ONLY likely resellers
    p.add_argument("--matched-only", action="store_true", help="Keep sellers with at least one AE match")
    p.add_argument("--min-high", type=int, default=0, help="Minimum high-score item count to keep seller")
    p.add_argument("--min-avg-profit", type=float, default=None, help="Minimum average profit (JPY) to keep seller")
    p.add_argument("--item-min-score", type=float, default=None, help="Minimum item score to include in per-item CSV (defaults to --score-threshold)")
    p.add_argument("--item-min-profit", type=float, default=None, help="Minimum item profit (JPY) to include in per-item CSV")
    p.add_argument("--delay-min", type=float, default=1.2)
    p.add_argument("--delay-max", type=float, default=2.2)

    args = p.parse_args(argv)

    cfg = Config()
    ae = AliExpressAdapter(cfg.aliexpress_app_key, cfg.aliexpress_app_secret, cfg.aliexpress_tracking_id)

    sellers = read_seller_candidates(args.inp)
    records: List[Dict[str, str | int | float]] = []
    per_items: Dict[str, List[ItemMatch]] = {}
    for row in sellers[: args.sellers]:
        sid = row.get("seller_id", "")
        surl = row.get("seller_url", "")
        if not sid or not surl:
            continue
        matches = verify_seller(
            seller_url=surl,
            ae=ae,
            items_per_seller=args.items_per_seller,
            pages_per_seller=args.pages_per_seller,
            per_item_candidates=args.per_item_candidates,
            delay_range=(args.delay_min, args.delay_max),
        )
        per_items[sid] = matches
        agg = aggregate_seller_result(matches, score_threshold=args.score_threshold)
        rec: Dict[str, str | int | float] = {
            "seller_id": sid,
            "seller_url": surl,
            "items_scanned": int(agg["items_scanned"]),
            "with_ae_candidates": int(agg["with_ae_candidates"]),
            "high_score_count": int(agg["high_score_count"]),
            "avg_score": float(agg["avg_score"]),
            "max_score": float(agg["max_score"]),
            "avg_profit_jpy": float(agg.get("avg_profit_jpy", 0.0)),
            "avg_margin_rate": float(agg.get("avg_margin_rate", 0.0)),
            "example_yahoo_url": str(agg["example_yahoo_url"]),
            "example_ae_url": str(agg["example_ae_url"]),
        }
        # Apply seller-level filters if requested
        keep = True
        if args.matched_only and rec["with_ae_candidates"] <= 0:
            keep = False
        if keep and args.min_high and rec["high_score_count"] < args.min_high:
            keep = False
        if keep and (args.min_avg_profit is not None) and rec["avg_profit_jpy"] < float(args.min_avg_profit):
            keep = False
        if keep:
            records.append(rec)
        # mild delay between sellers
        time.sleep(random.uniform(args.delay_min, args.delay_max))

    write_verified_csv(records, args.out)
    # Also write per-item details for visualization (apply per-item filters)
    items_out = args.out.replace(".csv", "_items.csv")
    # filter per item
    item_min_score = float(args.item_min_score) if args.item_min_score is not None else float(args.score_threshold)
    item_min_profit = float(args.item_min_profit) if args.item_min_profit is not None else None
    filtered: Dict[str, List[ItemMatch]] = {}
    for sid, items in per_items.items():
        if args.matched_only or item_min_score or item_min_profit is not None:
            sel: List[ItemMatch] = []
            for m in items:
                if args.matched_only and not m.ae_url:
                    continue
                if item_min_score and m.score < item_min_score:
                    continue
                if item_min_profit is not None:
                    try:
                        if not (isinstance(m.est_profit_jpy, (int, float)) and m.est_profit_jpy >= item_min_profit):
                            continue
                    except Exception:
                        continue
                sel.append(m)
            if sel:
                filtered[sid] = sel
        else:
            filtered[sid] = items
    write_item_details(filtered, items_out)
    print(f"Wrote: {args.out} (rows={len(records)})")
    print(f"Wrote: {items_out} (item-rows={sum(len(v) for v in per_items.values())})")
