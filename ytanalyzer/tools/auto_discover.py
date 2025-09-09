# -*- coding: utf-8 -*-
from __future__ import annotations

"""
Yutura auto-discover (headless)

順番ID (https://yutura.net/channel/{id}/) を少量ずつクロールして、
新規チャンネルを yutura_channels.ndjson に追記するワンショット CLI。

ポイント:
- 進捗は state JSON に保存 (next_id)
- cloudscraper で軽く取得、429/5xx は指数バックオフ
- 見つけたら {youtube_channel_url, channel_name, yutura_id, discovered_at} を NDJSON 追記
- 既存行との重複は許容（RSSウォッチャ側で無害）。必要なら --skip-duplicate を将来追加可。
"""

import argparse
import json
import os
import random
import re
import sys
import time
from datetime import datetime, timezone
from typing import Optional, Tuple

try:
    import cloudscraper
    from bs4 import BeautifulSoup
except Exception as e:  # pragma: no cover
    print("pip install cloudscraper beautifulsoup4", file=sys.stderr)
    raise


BASE = "https://yutura.net/channel/{id}/"


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def create_scraper(timeout: float) -> cloudscraper.CloudScraper:
    sc = cloudscraper.create_scraper(
        browser={"browser": "chrome", "platform": "windows", "mobile": False}
    )
    sc.headers.update({
        "Accept-Language": "ja,en;q=0.8",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
        ),
    })
    sc.timeout = timeout
    return sc


def fetch(sc: cloudscraper.CloudScraper, url: str, timeout: float, max_retries: int) -> Tuple[int, Optional[str]]:
    backoff = 1.0
    for _ in range(max_retries):
        try:
            r = sc.get(url, timeout=timeout)
            code = getattr(r, "status_code", 0)
            if code == 200:
                return code, r.text
            if code in (429,) or 500 <= code < 600:
                time.sleep(backoff)
                backoff = min(backoff * 2, 30.0)
                continue
            return code, None
        except Exception:
            time.sleep(backoff)
            backoff = min(backoff * 2, 30.0)
    return 0, None


def parse_channel(html: str) -> Tuple[Optional[str], Optional[str]]:
    """return (youtube_channel_url, channel_name)"""
    soup = BeautifulSoup(html, "html.parser")
    a = soup.find("a", href=re.compile(r"(https?://)?(www\.)?(youtube\.com|youtu\.be)/"))
    url = a.get("href") if a and a.has_attr("href") else None
    h1 = soup.find("h1")
    name = h1.get_text(" ", strip=True) if h1 else None
    return url, name


def load_state(path: str, start_id: int) -> int:
    try:
        with open(path, "r", encoding="utf-8") as f:
            d = json.load(f)
            n = int(d.get("next_id", start_id))
            return max(start_id, n)
    except Exception:
        return start_id


def save_state(path: str, next_id: int) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"next_id": int(next_id), "saved_at": utcnow_iso()}, f, ensure_ascii=False, indent=2)


def append_ndjson(path: str, obj: dict) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(obj, ensure_ascii=False))
        f.write("\n")


def run_once(
    out_path: str,
    state_path: str,
    start_id: int,
    batch: int,
    sleep_min: float,
    sleep_max: float,
    timeout: float,
    max_retries: int,
) -> int:
    sc = create_scraper(timeout)
    next_id = load_state(state_path, start_id)
    end_id = next_id + max(1, batch) - 1
    saved = 0
    for cid in range(next_id, end_id + 1):
        url = BASE.format(id=cid)
        code, text = fetch(sc, url, timeout, max_retries)
        if code != 200 or not text:
            # 404 等も進捗として next_id を進める
            save_state(state_path, cid + 1)
            time.sleep(random.uniform(max(0.0, sleep_min), max(sleep_min, sleep_max)))
            continue
        yurl, name = parse_channel(text)
        if yurl:
            append_ndjson(
                out_path,
                {
                    "youtube_channel_url": yurl,
                    "channel_name": name or None,
                    "yutura_id": cid,
                    "discovered_at": utcnow_iso(),
                    "source": "yutura",
                },
            )
            saved += 1
        save_state(state_path, cid + 1)
        time.sleep(random.uniform(max(0.0, sleep_min), max(sleep_min, sleep_max)))
    try:
        sc.close()
    except Exception:
        pass
    print(f"discover: tried={batch}, saved={saved}, next_id={end_id+1}")
    return saved


def build_arg_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Auto discover Yutura channels and append to NDJSON")
    ap.add_argument("--out", default=r"C:\\Users\\mouda\\yutura_channels.ndjson")
    ap.add_argument("--state", default="data/yutura_auto_discover.json")
    ap.add_argument("--start-id", type=int, default=1)
    ap.add_argument("--batch", type=int, default=200)
    ap.add_argument("--sleep-min", type=float, default=0.8)
    ap.add_argument("--sleep-max", type=float, default=2.0)
    ap.add_argument("--timeout", type=float, default=20.0)
    ap.add_argument("--max-retries", type=int, default=3)
    return ap


def main(argv: Optional[list[str]] = None) -> int:
    ap = build_arg_parser()
    a = ap.parse_args(argv)
    return run_once(
        out_path=a.out,
        state_path=a.state,
        start_id=a.start_id,
        batch=a.batch,
        sleep_min=a.sleep_min,
        sleep_max=a.sleep_max,
        timeout=a.timeout,
        max_retries=a.max_retries,
    )


if __name__ == "__main__":
    raise SystemExit(main())

