from __future__ import annotations

from typing import Dict, Generator, Iterable, List, Optional
import json
import time
import urllib.parse
import urllib.request


CDX_BASE = "https://web.archive.org/cdx/search/cdx"


def _build_cdx_url(
    url_pattern: str,
    to_ts: str = "20091231",
    match_type: str = "prefix",
    collapse: Optional[str] = "digest",
    fields: Iterable[str] = ("timestamp", "original"),
    from_ts: str = "2000",
    filters: Optional[Iterable[str]] = None,
    page_size: Optional[int] = None,
    page: Optional[int] = None,
) -> str:
    params = {
        "url": url_pattern,
        "output": "json",
        "from": from_ts,
        "to": to_ts,
        "matchType": match_type,
        "fl": ",".join(fields),
    }
    if collapse:
        params["collapse"] = collapse
    if filters:
        # Use list to emit multiple filter= entries
        params["filter"] = list(filters)
    if page_size is not None:
        params["limit"] = int(page_size)
    if page is not None:
        params["page"] = int(page)
    return CDX_BASE + "?" + urllib.parse.urlencode(params, safe=",:*", doseq=True)


def cdx_latest_before(original_url: str, to_ts: str = "20091231", fields: Iterable[str] = ("timestamp", "original")) -> Optional[Dict[str, str]]:
    """Return the latest snapshot row at or before to_ts for an exact URL."""
    url = _build_cdx_url(
        original_url,
        to_ts=to_ts,
        match_type="exact",
        collapse=None,
        fields=fields,
        from_ts="2000",
        filters=None,
        page_size=50,
        page=0,
    )
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            raw = resp.read()
        data = json.loads(raw)
        if not data or len(data) <= 1:
            return None
        header: List[str] = data[0]
        # choose the last row (latest)
        row = data[-1]
        return {k: v for k, v in zip(header, row)}
    except Exception:
        return None


def cdx_iter(
    url_pattern: str,
    to_ts: str = "20091231",
    match_type: str = "prefix",
    collapse: Optional[str] = "digest",
    fields: Iterable[str] = ("timestamp", "original"),
    pause_sec: float = 0.1,
    from_ts: str = "2000",
    filters: Optional[Iterable[str]] = None,
    page_size: int = 500,
    max_pages: int = 20,
    limit_total: Optional[int] = None,
) -> Generator[Dict[str, str], None, None]:
    yielded = 0
    for page in range(max_pages):
        url = _build_cdx_url(
            url_pattern,
            to_ts=to_ts,
            match_type=match_type,
            collapse=collapse,
            fields=fields,
            from_ts=from_ts,
            filters=filters,
            page_size=page_size,
            page=page,
        )
        # Basic retry for CDX endpoint
        last_err: Optional[Exception] = None
        for attempt in range(4):
            try:
                with urllib.request.urlopen(url, timeout=60) as resp:
                    raw = resp.read()
                last_err = None
                break
            except Exception as e:  # noqa: BLE001
                last_err = e
                time.sleep(min(5, 1.5 * (attempt + 1)))
        if last_err is not None:
            # Give up this page; stop iteration
            break
        data = json.loads(raw)
        if not data or len(data) <= 1:
            break
        header: List[str] = data[0]
        rows = data[1:]
        for row in rows:
            yield {k: v for k, v in zip(header, row)}
            yielded += 1
            if limit_total is not None and yielded >= limit_total:
                return
            if pause_sec:
                time.sleep(pause_sec)
        if limit_total is not None and yielded >= limit_total:
            return
