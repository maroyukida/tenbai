# -*- coding: utf-8 -*-
from __future__ import annotations

import typer

from typing import Optional

from .config import Config
from .webapp.app import create_app


app = typer.Typer(help="YTAnalyzer CLI (rss-watch, rss-export, api-fetch, api-refetch, growth-rank, serve)")


@app.command("rss-watch")
def rss_watch(
    channels_file: str = typer.Option(..., help="NDJSON of channels (includes youtube_channel_url)"),
    db: str = typer.Option("data/rss_watch.sqlite", help="SQLite db path"),
    concurrency: int = typer.Option(200),
    rps: float = typer.Option(15.0, help="Requests per second"),
    batch: int = typer.Option(800, help="Batch per tick"),
    tick: int = typer.Option(5, help="Tick seconds"),
    once: bool = typer.Option(False, help="Run a single batch and exit"),
    limit: int = typer.Option(0, help="Max channels when --once"),
):
    from .services import rss_watcher
    argv = [
        "--channels-file", channels_file,
        "--db", db,
        "--concurrency", str(concurrency),
        "--rps", str(rps),
        "--batch", str(batch),
        "--tick", str(tick),
    ]
    if once:
        argv.append("--once")
        if limit:
            argv += ["--limit", str(limit)]
    rss_watcher.main(argv)


@app.command("rss-export")
def rss_export(
    db: str = typer.Option("data/rss_watch.sqlite"),
    out_dir: str = typer.Option("exports"),
    window_minutes: int = typer.Option(10),
    loop: bool = typer.Option(False),
    min_published_hours: int = typer.Option(48),
):
    from .services import rss_export
    argv = [
        "--db", db,
        "--out-dir", out_dir,
        "--window-minutes", str(window_minutes),
        "--min-published-hours", str(min_published_hours),
    ]
    if loop:
        argv.append("--loop")
    rss_export.main(argv)


@app.command("api-fetch")
def api_fetch(
    db: str = typer.Option("data/rss_watch.sqlite"),
    in_dir: str = typer.Option("exports"),
    api_key: Optional[str] = typer.Option(None, help="YouTube API key (env YOUTUBE_API_KEY as default)"),
    batch_size: int = typer.Option(50),
    qps: float = typer.Option(1.0),
    all_files: bool = typer.Option(False),
    max_files: int = typer.Option(0),
):
    from .services import api_fetcher
    argv = [
        "--db", db,
        "--in-dir", in_dir,
        "--batch-size", str(batch_size),
        "--qps", str(qps),
    ]
    if api_key:
        argv += ["--api-key", api_key]
    if all_files:
        argv.append("--all-files")
    if max_files:
        argv += ["--max-files", str(max_files)]
    api_fetcher.main(argv)


@app.command("api-refetch")
def api_refetch(
    db: str = typer.Option("data/rss_watch.sqlite"),
    api_key: Optional[str] = typer.Option(None, help="YouTube API key (env YOUTUBE_API_KEY as default)"),
    qps: float = typer.Option(1.5),
    tol_minutes: int = typer.Option(15),
    window_hours: int = typer.Option(30),
    max_ids: int = typer.Option(0),
    batch_size: int = typer.Option(50),
):
    from .services import api_refetch as ref
    argv = [
        "--db", db,
        "--qps", str(qps),
        "--tol-minutes", str(tol_minutes),
        "--window-hours", str(window_hours),
        "--batch-size", str(batch_size),
    ]
    if api_key:
        argv += ["--api-key", api_key]
    if max_ids:
        argv += ["--max-ids", str(max_ids)]
    ref.main(argv)


@app.command("growth-rank")
def growth_rank(
    db: str = typer.Option("data/rss_watch.sqlite"),
    window_hours: int = typer.Option(48),
    tol_minutes: int = typer.Option(20),
    max_videos: int = typer.Option(10000),
):
    from .services import growth_ranker
    argv = [
        "--db", db,
        "--window-hours", str(window_hours),
        "--tol-minutes", str(tol_minutes),
        "--max-videos", str(max_videos),
    ]
    growth_ranker.main(argv)


@app.command("yutura-day-scrape")
def yutura_day_scrape(
    db: str = typer.Option("data/rss_watch.sqlite"),
    date: str = typer.Option(..., help="YYYYMMDD"),
    mode: str = typer.Option("view"),
    pages: int = typer.Option(3),
):
    from .services import yutura_day_scraper
    argv = [
        "--db", db,
        "--date", date,
        "--mode", mode,
        "--pages", str(pages),
    ]
    yutura_day_scraper.main(argv)


@app.command("channel-fetch")
def channel_fetch(
    db: str = typer.Option("data/rss_watch.sqlite"),
    api_key: Optional[str] = typer.Option(None),
    qps: float = typer.Option(1.0),
    batch_size: int = typer.Option(50),
    max_channels: int = typer.Option(0),
):
    from .services import channel_fetcher
    argv = [
        "--db", db,
        "--qps", str(qps),
        "--batch-size", str(batch_size),
    ]
    if api_key:
        argv += ["--api-key", api_key]
    if max_channels:
        argv += ["--max-channels", str(max_channels)]
    channel_fetcher.main(argv)


@app.command("day-rank-channels")
def day_rank_channels(
    db: str = typer.Option("data/rss_watch.sqlite"),
    date: str = typer.Option(None, help="YYYY-MM-DD or YYYYMMDD; default=yesterday (JST)"),
):
    from .services import day_ranker
    argv = ["--db", db]
    if date:
        argv += ["--date", date]
    day_ranker.main(argv)

@app.command("week-rank-channels")
def week_rank_channels(
    db: str = typer.Option("data/rss_watch.sqlite"),
    end_date: str = typer.Option(None, help="YYYY-MM-DD or YYYYMMDD; default=yesterday (JST)"),
):
    from .services import week_ranker
    argv = ["--db", db]
    if end_date:
        argv += ["--end-date", end_date]
    week_ranker.main(argv)

@app.command("serve")
def serve(host: str = typer.Option("127.0.0.1"), port: int = typer.Option(3500)):
    cfg = Config()
    fapp = create_app(cfg)
    fapp.run(host=host, port=port, debug=False)


@app.command("import-watchlist")
def import_watchlist(
    json_path: str = typer.Option(..., help="Path to youtube_channels_full.json (array)"),
    db: str = typer.Option("data/rss_watch.sqlite", help="SQLite db path"),
    no_ndjson: bool = typer.Option(False, help="Do not emit data/watchlist_channels.ndjson"),
    no_seed: bool = typer.Option(False, help="Do not seed rss_channels"),
):
    from .tools import watchlist_import as wi
    argv = [
        "--json", json_path,
        "--db", db,
    ]
    if no_ndjson:
        argv.append("--no-ndjson")
    if no_seed:
        argv.append("--no-seed")
    wi.main(argv)


@app.command("resale-mvp")
def resale_mvp(
    input_urls: str = typer.Option(None, help="Text file of Yahoo item URLs (one per line)", rich_help_panel="Input"),
    seller_url: str = typer.Option(None, help="Yahoo seller listing URL", rich_help_panel="Input"),
    seller_pages: int = typer.Option(1, help="Pages to crawl when --seller-url is set"),
    out: str = typer.Option("exports/resale_candidates.csv", help="Output CSV path"),
    per_item_candidates: int = typer.Option(3, help="AE candidates per Yahoo item"),
    delay_min: float = typer.Option(1.2),
    delay_max: float = typer.Option(2.2),
):
    """Run Yahoo x AliExpress resale MVP matcher.

    Note: AliExpress official API credentials (env) are optional. If missing,
    the tool runs but cannot fetch AE candidates and will mark rows accordingly.
    """
    from .services import resale_mvp as rm
    argv = []
    if input_urls:
        argv += ["--input-urls", input_urls]
    if seller_url:
        argv += ["--seller-url", seller_url, "--seller-pages", str(seller_pages)]
    argv += [
        "--out", out,
        "--per-item-candidates", str(per_item_candidates),
        "--delay-min", str(delay_min),
        "--delay-max", str(delay_max),
    ]
    rm.main(argv)


@app.command("resale-find-sellers")
def resale_find_sellers(
    seed_urls: str = typer.Option(None, help="Text file of seed URLs (search/category/item)"),
    keywords: str = typer.Option(None, help="Text file of keywords (one per line)"),
    pages_per_keyword: int = typer.Option(1),
    per_page: int = typer.Option(50),
    sample_items_per_seller: int = typer.Option(5),
    total_item_cap: int = typer.Option(400),
    out: str = typer.Option("exports/seller_candidates.csv"),
    top_k: int = typer.Option(200),
    min_items: int = typer.Option(2),
    min_hit_rate: float = typer.Option(0.2),
    min_overseas_rate: float = typer.Option(0.5, help="Keep sellers with >= this overseas-rate"),
    min_overseas: int = typer.Option(1, help="Keep sellers with >= this count of overseas items"),
    delay_min: float = typer.Option(1.0),
    delay_max: float = typer.Option(2.2),
):
    """Discover sellers likely doing AE転売（ヒューリスティック）。

    入力は検索/カテゴリ/商品ページのURL群（seed）と、任意のキーワード。
    タイトルに含まれる典型語（海外倉庫, 未塗装, 1/35, TPE など）の出現率を
    セラー単位で集計してスコア化します。
    """
    from .services import seller_finder as sf
    argv = []
    if seed_urls:
        argv += ["--seed-urls", seed_urls]
    if keywords:
        argv += ["--keywords", keywords]
    argv += [
        "--pages-per-keyword", str(pages_per_keyword),
        "--per-page", str(per_page),
        "--sample-items-per-seller", str(sample_items_per_seller),
        "--total-item-cap", str(total_item_cap),
        "--out", out,
        "--top-k", str(top_k),
        "--min-items", str(min_items),
        "--min-hit-rate", str(min_hit_rate),
        "--min-overseas-rate", str(min_overseas_rate),
        "--min-overseas", str(min_overseas),
        "--delay-min", str(delay_min),
        "--delay-max", str(delay_max),
    ]
    sf.main(argv)

@app.command("resale-verify-sellers")
def resale_verify_sellers(
    inp: str = typer.Option("exports/seller_candidates.csv", help="Input seller candidates CSV"),
    out: str = typer.Option("exports/seller_verified.csv", help="Output CSV of verification results"),
    sellers: int = typer.Option(10, help="Number of top sellers to verify"),
    items_per_seller: int = typer.Option(3),
    pages_per_seller: int = typer.Option(1),
    per_item_candidates: int = typer.Option(3),
    score_threshold: float = typer.Option(0.72),
    matched_only: bool = typer.Option(False, help="Keep only sellers with at least one AE match"),
    min_high: int = typer.Option(0, help="Min high-score item count to keep seller"),
    min_avg_profit: float = typer.Option(0.0, help="Min average profit (JPY) to keep seller (0 disables)"),
    item_min_score: float = typer.Option(None, help="Min item score to include in per-item CSV (default: score_threshold)"),
    item_min_profit: float = typer.Option(None, help="Min item profit (JPY) to include in per-item CSV"),
    delay_min: float = typer.Option(1.2),
    delay_max: float = typer.Option(2.2),
):
    """Verify top seller candidates by sampling items and scoring AE matches.

    AliExpress公式APIキーが未設定の場合、候補取得ができずスコアは低めになります。
    .env に `ALIEXPRESS_APP_KEY/SECRET/TRACKING_ID` を設定すると有効化されます。
    """
    from .services import seller_verify as sv
    argv = [
        "--in", inp,
        "--out", out,
        "--sellers", str(sellers),
        "--items-per-seller", str(items_per_seller),
        "--pages-per-seller", str(pages_per_seller),
        "--per-item-candidates", str(per_item_candidates),
        "--score-threshold", str(score_threshold),
        "--delay-min", str(delay_min),
        "--delay-max", str(delay_max),
    ]
    if matched_only:
        argv.append("--matched-only")
    if min_high:
        argv += ["--min-high", str(min_high)]
    if min_avg_profit and float(min_avg_profit) != 0.0:
        argv += ["--min-avg-profit", str(min_avg_profit)]
    if item_min_score is not None:
        argv += ["--item-min-score", str(item_min_score)]
    if item_min_profit is not None:
        argv += ["--item-min-profit", str(item_min_profit)]
    sv.main(argv)

@app.command("resale-ae-check")
def resale_ae_check(q: str = typer.Option("iphone case"), n: int = typer.Option(3)):
    """Check AliExpress API connectivity with current .env keys."""
    from .tools import ae_check
    ae_check.main(["--q", q, "--n", str(n)])


def main():
    app()


if __name__ == "__main__":
    main()
