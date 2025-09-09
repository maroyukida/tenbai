# -*- coding: utf-8 -*-
import requests, json, os, time, random, logging
try:
    import cloudscraper
except Exception:
    cloudscraper = None

DEFAULT_HEADERS = {
    "User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language":"ja,en;q=0.9","Accept":"text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer":"https://yutura.net/","Cache-Control":"no-cache",
}
logger = logging.getLogger(__name__)

def load_cookies_txt(path):
    jar=requests.cookies.RequestsCookieJar()
    if not path or not os.path.exists(path): return jar
    with open(path,"r",encoding="utf-8") as f:
        for line in f:
            if not line.strip() or line.startswith("#"): continue
            p=line.strip().split("\t")
            if len(p)!=7: continue
            domain,_,cookie_path,_,_,name,value=p
            jar.set(name,value,domain=domain,path=cookie_path)
    return jar

def load_cookies_json(path):
    jar=requests.cookies.RequestsCookieJar()
    if not path or not os.path.exists(path): return jar
    with open(path,"r",encoding="utf-8") as f:
        for c in json.load(f):
            name,value=c.get("name"),c.get("value")
            if name and value: jar.set(name,value,domain=c.get("domain","yutura.net"),path=c.get("path","/"))
    return jar

def build_session(use_cloudscraper=True, cookies_txt=None, cookies_json=None, extra_cookie_header=None):
    s = cloudscraper.create_scraper(browser={"browser":"chrome","platform":"windows","mobile":False}) if (use_cloudscraper and cloudscraper) else requests.Session()
    s.headers.update(DEFAULT_HEADERS)
    jar=requests.cookies.RequestsCookieJar()
    if cookies_txt: jar.update(load_cookies_txt(cookies_txt))
    if cookies_json: jar.update(load_cookies_json(cookies_json))
    s.cookies.update(jar)
    if extra_cookie_header:
        s.headers["Cookie"] = extra_cookie_header
    return s

def fetch_html(session, url, *, retry=5, timeout=30, base_wait=0.4, cooldown_429=90):
    wait=base_wait; last=None
    for _ in range(retry+1):
        r=session.get(url,timeout=timeout); last=r.status_code
        if r.status_code==200:
            time.sleep(base_wait + random.uniform(0,0.25)); return r.text
        if r.status_code==429:
            ra=r.headers.get("Retry-After")
            sec=int(ra) if (ra and str(ra).isdigit()) else cooldown_429
            sec=min(sec,180); logger.warning(f"429 → sleep {sec}s ({url})"); time.sleep(sec + random.uniform(0,3)); continue
        if 500<=r.status_code<600:
            time.sleep(wait + random.uniform(0,0.6)); wait=min(wait*1.7,15); continue
        time.sleep(wait + random.uniform(0,0.5)); wait=min(wait*1.5,10)
    raise RuntimeError(f"HTTP {last} for {url}")
