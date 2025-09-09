from __future__ import annotations

import html
import re
import time
from typing import Iterable, List

import requests
from urllib.parse import urlparse, parse_qs, unquote


def _ddg_unwrap(url: str) -> str:
    # DuckDuckGo HTML may return /l/?uddg=<encoded>
    try:
        p = urlparse(url)
        if p.netloc.endswith("duckduckgo.com") and p.path.startswith("/l/"):
            q = parse_qs(p.query)
            if "uddg" in q:
                return unquote(q["uddg"][0])
    except Exception:
        pass
    return url


def ddg_search_html(query: str, *, max_results: int = 20, region: str = "jp-jp", pause_sec: float = 1.0) -> List[str]:
    """Lightweight DuckDuckGo HTML search to collect result URLs.
    Avoids scraping Google due to TOS. Results are fed to Wayback availability later.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
        "Accept-Language": "ja,en;q=0.9",
    }
    params = {
        "q": query,
        "kl": region,
    }
    urls: List[str] = []
    try:
        r = requests.get("https://duckduckgo.com/html/", params=params, headers=headers, timeout=20)
        r.raise_for_status()
    except Exception:
        return urls

    # Extract result links; tolerate slight template differences
    # pattern for anchor href in result entries
    link_re = re.compile(r'<a[^>]+class="[^"]*result__a[^"]*"[^>]+href="([^"]+)"', re.I)
    for m in link_re.finditer(r.text):
        href = html.unescape(m.group(1))
        u = _ddg_unwrap(href)
        if u.startswith("http"):
            urls.append(u)
        if len(urls) >= max_results:
            break
    # Fallback: any result__url__domain anchors
    if not urls:
        generic_re = re.compile(r'<a[^>]+href="([^"]+)"[^>]*>(?:<b>)?https?://', re.I)
        for m in generic_re.finditer(r.text):
            href = html.unescape(m.group(1))
            u = _ddg_unwrap(href)
            if u.startswith("http") and u not in urls:
                urls.append(u)
            if len(urls) >= max_results:
                break
    time.sleep(pause_sec)
    return urls

