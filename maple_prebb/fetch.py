from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

import requests


@dataclass
class FetchResponse:
    url: str
    status_code: int
    headers: dict
    content: bytes


class WaybackFetcher:
    def __init__(self, rps: float = 1.5, timeout: int = 20, retries: int = 3):
        self.timeout = timeout
        self.retries = retries
        self._session = requests.Session()
        self._min_interval = 1.0 / max(0.01, rps)
        self._last_at = 0.0

    def _rate_limit(self):
        now = time.time()
        delta = now - self._last_at
        if delta < self._min_interval:
            time.sleep(self._min_interval - delta)
        self._last_at = time.time()

    def fetch(self, url: str) -> FetchResponse:
        attempt = 0
        while True:
            self._rate_limit()
            try:
                r = self._session.get(url, timeout=self.timeout)
                return FetchResponse(url=r.url, status_code=r.status_code, headers=dict(r.headers), content=r.content)
            except Exception as e:  # noqa: BLE001
                attempt += 1
                if attempt > self.retries:
                    raise e
                time.sleep(min(5, attempt * 1.5))

    def close(self):
        try:
            self._session.close()
        except Exception:
            pass

