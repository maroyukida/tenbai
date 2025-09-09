import argparse
from pathlib import Path
import sys

from .config import load_config
from .cdx import cdx_iter, cdx_latest_before
from .fetch import WaybackFetcher
from .warc import WarcOrFolderWriter
from .parse import extract_text_and_title
from .index import Indexer
from .availability import availability
from .search import ddg_search_html


def cmd_crawl(args: argparse.Namespace) -> int:
    cfg = load_config(Path(args.config))

    warc_dir = Path(args.warc_dir or cfg.get("store", {}).get("warc_dir", "./archive/warc"))
    meta_dir = Path(args.meta_dir or cfg.get("store", {}).get("meta_dir", "./archive/meta"))
    index_path = Path(args.index or cfg.get("store", {}).get("index", "./index/maple.db"))

    warc_dir.mkdir(parents=True, exist_ok=True)
    meta_dir.mkdir(parents=True, exist_ok=True)
    index_path.parent.mkdir(parents=True, exist_ok=True)

    rps = float(cfg.get("fetch", {}).get("rps", 1.5))
    timeout = int(cfg.get("fetch", {}).get("timeout_sec", 20))
    retries = int(cfg.get("fetch", {}).get("retries", 3))
    to_ts = str(cfg.get("time_range", {}).get("to", "20091231"))
    from_ts = str(cfg.get("time_range", {}).get("from", "2000"))

    cdx_defaults = cfg.get("cdx", {})
    collapse = cdx_defaults.get("collapse", "digest")
    fields = cdx_defaults.get(
        "fields",
        ["timestamp", "original", "mimetype", "statuscode", "digest", "length"],
    )
    filters = cdx_defaults.get("filters")

    fetcher = WaybackFetcher(rps=rps, timeout=timeout, retries=retries)
    writer = WarcOrFolderWriter(warc_dir=warc_dir, meta_dir=meta_dir)
    indexer = Indexer(index_path)

    limit = args.limit if args.limit is not None else None
    count = 0
    seen_digests = set()

    sources = cfg.get("sources", [])
    if not sources:
        print("No sources defined in config.", file=sys.stderr)
        return 2

    content_filter = cfg.get("content_filter", {})
    keywords_any = content_filter.get("keywords_any")

    for src in sources:
        pattern = src.get("pattern")
        match = src.get("match", "prefix")
        if not pattern:
            continue
        for row in cdx_iter(
            url_pattern=pattern,
            to_ts=to_ts,
            match_type=match,
            collapse=collapse,
            fields=fields,
            from_ts=from_ts,
            filters=filters,
            page_size=int(cdx_defaults.get("page_size", 500)),
            max_pages=int(cdx_defaults.get("max_pages", 20)),
            limit_total=args.limit or None,
        ):
            # Basic de-dup via digest when available
            digest = row.get("digest")
            if digest and digest in seen_digests:
                continue

            wb_url = f"https://web.archive.org/web/{row['timestamp']}/{row['original']}"
            try:
                resp = fetcher.fetch(wb_url)
            except Exception as e:  # noqa: BLE001
                print(f"FETCH-ERR {wb_url}: {e}", file=sys.stderr)
                continue

            try:
                rec_info = writer.write(row=row, response=resp)
            except Exception as e:  # noqa: BLE001
                print(f"WRITE-ERR {wb_url}: {e}", file=sys.stderr)
                continue

            try:
                text, title, charset = extract_text_and_title(resp.content)
            except Exception:
                text, title, charset = "", "", None

            # Optional content keyword filter to keep only Maple-related pages
            if keywords_any:
                blob = (title or "") + "\n" + (text or "")
                if not any(k.lower() in blob.lower() for k in keywords_any):
                    continue

            try:
                indexer.add(
                    url=row.get("original", ""),
                    wayback_timestamp=row.get("timestamp", ""),
                    status=row.get("statuscode"),
                    mimetype=row.get("mimetype"),
                    digest=digest,
                    title=title,
                    text=text,
                    charset=charset,
                    meta_path=str(rec_info.get("meta_path")) if rec_info else None,
                    warc_path=str(rec_info.get("warc_path")) if rec_info else None,
                )
            except Exception as e:  # noqa: BLE001
                print(f"INDEX-ERR {wb_url}: {e}", file=sys.stderr)

            if digest:
                seen_digests.add(digest)

            count += 1
            if limit is not None and count >= limit:
                print(f"Reached limit {limit}.")
                indexer.close()
                fetcher.close()
                return 0

    indexer.close()
    fetcher.close()
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    index_path = Path(args.index or "./index/maple.db")
    indexer = Indexer(index_path)
    try:
        results = indexer.search(args.query, year=args.year, limit=args.limit)
        for row in results:
            ts = row.get("wayback_timestamp", "")
            print(f"{row['title'][:60] if row['title'] else '(no title)'}\n  {row['url']}\n  {ts}\n")
    finally:
        indexer.close()
    return 0


def cmd_replay(args: argparse.Namespace) -> int:
    warc_dir = Path(args.warc_dir or "./archive/warc")
    collection = args.collection or "maple"
    host = args.host or "127.0.0.1"
    port = int(args.port or 8080)

    if not args.auto:
        print("To replay your WARC locally with pywb:")
        print("  pip install pywb")
        print(f"  wb-manager init {collection}")
        print(f"  wb-manager add {collection} \"{warc_dir}/*.warc*\"")
        print(f"  wayback --collections {collection} --host {host} --port {port}")
        print(f"Then open http://{host}:{port}/ in your browser.")
        return 0

    # Auto mode: try to set up and start pywb if available
    import shutil
    import subprocess
    import glob

    wb = shutil.which("wb-manager")
    wayback = shutil.which("wayback")
    if not wb or not wayback:
        print("pywb not found. Please run: pip install pywb", file=sys.stderr)
        return 2

    warc_files = sorted(glob.glob(str(warc_dir / "*.warc*")))
    if not warc_files:
        print("No WARC files found in", warc_dir, file=sys.stderr)
        print("Install warcio and recrawl to generate WARCs:")
        print("  pip install warcio")
        print("  python -m maple_prebb crawl <seeds.yaml>")
        return 2

    # Ensure collection exists
    subprocess.run([wb, "list"], check=False)
    init_res = subprocess.run([wb, "init", collection], check=False, capture_output=True, text=True)
    if init_res.returncode != 0 and "already exists" not in (init_res.stderr or "") + (init_res.stdout or ""):
        print(init_res.stdout)
        print(init_res.stderr, file=sys.stderr)
        print("Failed to init pywb collection.", file=sys.stderr)
        return 2

    # Add warc files
    for wf in warc_files:
        subprocess.run([wb, "add", collection, wf], check=False)

    # Start wayback server (non-blocking)
    proc = subprocess.Popen([wayback, "--collections", collection, "--host", host, "--port", str(port)])
    print(f"pywb started (PID {proc.pid}). Open http://{host}:{port}/")
    print("Stop with Ctrl+C in that terminal or kill the PID.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="maple-prebb", description="Pre-2009 Maple crawler (Wayback-driven)")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_crawl = sub.add_parser("crawl", help="CDX list -> fetch -> store -> index")
    p_crawl.add_argument("config", help="Path to seeds/config YAML")
    p_crawl.add_argument("--limit", type=int, default=None, help="Max pages to process")
    p_crawl.add_argument("--warc-dir", default=None)
    p_crawl.add_argument("--meta-dir", default=None)
    p_crawl.add_argument("--index", default=None)
    p_crawl.set_defaults(func=cmd_crawl)

    p_search = sub.add_parser("search", help="Search indexed pages")
    p_search.add_argument("query")
    p_search.add_argument("--year", type=int, default=None)
    p_search.add_argument("--limit", type=int, default=20)
    p_search.add_argument("--index", default=None)
    p_search.set_defaults(func=cmd_search)

    p_replay = sub.add_parser("replay", help="Replay WARC via pywb (auto or manual)")
    p_replay.add_argument("start", nargs="?", help="(optional) keep for compatibility")
    p_replay.add_argument("--warc-dir", default=None, help="Directory containing WARC files")
    p_replay.add_argument("--collection", default="maple", help="pywb collection name")
    p_replay.add_argument("--host", default="127.0.0.1")
    p_replay.add_argument("--port", type=int, default=8080)
    p_replay.add_argument("--auto", action="store_true", help="Init/add and start pywb automatically")
    p_replay.set_defaults(func=cmd_replay)

    p_grab = sub.add_parser("grab", help="Fetch specific URLs via Wayback Availability API")
    p_grab.add_argument("urls", nargs="+", help="Original URLs to fetch (not Wayback URLs)")
    p_grab.add_argument("--ts", default="20091231", help="Target timestamp for closest snapshot")
    p_grab.add_argument("--warc-dir", default="./archive/warc")
    p_grab.add_argument("--meta-dir", default="./archive/meta")
    p_grab.add_argument("--index", default="./index/maple_grab.db")
    p_grab.set_defaults(func=cmd_grab)

    p_gs = sub.add_parser("grab-search", help="Search the web (DuckDuckGo HTML) and grab Wayback snapshots")
    p_gs.add_argument("-q", "--query", action="append", dest="queries", help="Query (repeatable)")
    p_gs.add_argument("--queries-file", help="File with one query per line")
    p_gs.add_argument("--per", type=int, default=10, help="Results per query")
    p_gs.add_argument("--ts", default="20091231", help="Target timestamp for snapshot")
    p_gs.add_argument("--warc-dir", default="./archive/warc")
    p_gs.add_argument("--meta-dir", default="./archive/meta")
    p_gs.add_argument("--index", default="./index/maple_search.db")
    p_gs.add_argument("--strict", action="store_true", help="Skip snapshots newer than target ts")
    p_gs.set_defaults(func=cmd_grab_search)

    return p


def main(argv=None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


def cmd_grab(args: argparse.Namespace) -> int:
    warc_dir = Path(args.warc_dir)
    meta_dir = Path(args.meta_dir)
    index_path = Path(args.index)
    warc_dir.mkdir(parents=True, exist_ok=True)
    meta_dir.mkdir(parents=True, exist_ok=True)
    index_path.parent.mkdir(parents=True, exist_ok=True)

    fetcher = WaybackFetcher(rps=1.0, timeout=30, retries=3)
    writer = WarcOrFolderWriter(warc_dir=warc_dir, meta_dir=meta_dir)
    indexer = Indexer(index_path)

    for original in args.urls:
        # Prefer a snapshot at/before the target timestamp
        ts = None
        wb_url = None
        row = cdx_latest_before(original, args.ts, fields=("timestamp", "original"))
        if row:
            ts = row.get("timestamp")
            wb_url = f"https://web.archive.org/web/{ts}/{original}"
        if not wb_url:
            closest = None
            try:
                closest = availability(original, args.ts)
            except Exception as e:  # noqa: BLE001
                print(f"AVAIL-ERR {original}: {e}")
                continue
            if not closest:
                print(f"No snapshot for {original}")
                continue
            wb_url = closest.get("url")
            ts = closest.get("timestamp")
        try:
            resp = fetcher.fetch(wb_url)
        except Exception as e:  # noqa: BLE001
            print(f"FETCH-ERR {wb_url}: {e}")
            continue

        row = {"timestamp": ts, "original": original, "mimetype": resp.headers.get("Content-Type"), "statuscode": resp.status_code, "digest": None}
        rec_info = writer.write(row=row, response=resp)
        try:
            text, title, charset = extract_text_and_title(resp.content)
        except Exception:
            text, title, charset = "", "", None
        indexer.add(
            url=original,
            wayback_timestamp=ts or "",
            status=resp.status_code,
            mimetype=resp.headers.get("Content-Type"),
            digest=None,
            title=title,
            text=text,
            charset=charset,
            meta_path=str(rec_info.get("meta_path")) if rec_info else None,
            warc_path=str(rec_info.get("warc_path")) if rec_info else None,
        )

    indexer.close()
    fetcher.close()
    return 0


def _iter_queries(args: argparse.Namespace):
    qs = []
    if args.queries:
        qs.extend([q for q in args.queries if q])
    if args.queries_file:
        p = Path(args.queries_file)
        if p.exists():
            qs.extend([line.strip() for line in p.read_text(encoding="utf-8").splitlines() if line.strip()])
    return qs


def cmd_grab_search(args: argparse.Namespace) -> int:
    warc_dir = Path(args.warc_dir)
    meta_dir = Path(args.meta_dir)
    index_path = Path(args.index)
    warc_dir.mkdir(parents=True, exist_ok=True)
    meta_dir.mkdir(parents=True, exist_ok=True)
    index_path.parent.mkdir(parents=True, exist_ok=True)

    fetcher = WaybackFetcher(rps=1.0, timeout=30, retries=3)
    writer = WarcOrFolderWriter(warc_dir=warc_dir, meta_dir=meta_dir)
    indexer = Indexer(index_path)

    queries = _iter_queries(args)
    if not queries:
        print("No queries provided. Use -q or --queries-file.")
        return 2

    seen = set()
    total_added = 0
    for q in queries:
        urls = ddg_search_html(q, max_results=args.per)
        for u in urls:
            if u in seen:
                continue
            seen.add(u)
            ts = None
            wb_url = None
            row = cdx_latest_before(u, args.ts, fields=("timestamp", "original"))
            if row:
                ts = row.get("timestamp")
                wb_url = f"https://web.archive.org/web/{ts}/{u}"
            if not wb_url:
                try:
                    closest = availability(u, args.ts)
                except Exception as e:  # noqa: BLE001
                    print(f"AVAIL-ERR {u}: {e}")
                    continue
                if not closest:
                    continue
                wb_url = closest.get("url")
                ts = closest.get("timestamp")
            try:
                resp = fetcher.fetch(wb_url)
            except Exception as e:  # noqa: BLE001
                print(f"FETCH-ERR {wb_url}: {e}")
                continue
            if args.strict and ts and ts > args.ts:
                # discard newer-than-target snapshots when strict
                continue
            row = {"timestamp": ts, "original": u, "mimetype": resp.headers.get("Content-Type"), "statuscode": resp.status_code, "digest": None}
            rec_info = writer.write(row=row, response=resp)
            try:
                text, title, charset = extract_text_and_title(resp.content)
            except Exception:
                text, title, charset = "", "", None
            indexer.add(
                url=u,
                wayback_timestamp=ts or "",
                status=resp.status_code,
                mimetype=resp.headers.get("Content-Type"),
                digest=None,
                title=title,
                text=text,
                charset=charset,
                meta_path=str(rec_info.get("meta_path")) if rec_info else None,
                warc_path=str(rec_info.get("warc_path")) if rec_info else None,
            )
            total_added += 1

    indexer.close()
    fetcher.close()
    print(f"Added {total_added} pages from search.")
    return 0
