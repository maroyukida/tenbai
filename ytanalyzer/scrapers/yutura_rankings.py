# -*- coding: utf-8 -*-
import logging
from bs4 import BeautifulSoup
from datetime import datetime
from .http import build_session, fetch_html

BASE = "https://yutura.net"
logger = logging.getLogger(__name__)

def crawl_ranking_day(date_yyyymmdd: str, mode: str, pages: int = 1):
    """yutura 日別ランキングから channel_id を列挙"""
    result_chids = []
    s=build_session(use_cloudscraper=True)
    for page in range(1, pages + 1):
        url = f"{BASE}/ranking/{mode}/daily/{date_yyyymmdd}/{page}"
        html = fetch_html(s, url)
        soup = BeautifulSoup(html, "lxml")
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "/channel/" in href:
                try:
                    chid = int(href.split("/channel/")[1].split("/")[0])
                    result_chids.append(chid)
                except Exception:
                    continue
    return result_chids
