# -*- coding: utf-8 -*-
import re, time, logging
from urllib.parse import urljoin, urlparse
from datetime import datetime, timezone
from bs4 import BeautifulSoup

from .http import build_session, fetch_html
from ..db import Database

BASE = "https://yutura.net"
LIST_URL = f"{BASE}/banned/"
logger = logging.getLogger(__name__)

NON_VIDEO_WORDS = {"マイページ","推薦","ニュース","ランキング","投稿","お気に入り","タグ","記事","ユーチュラ","Yutura","最新情報","関連","チャンネル推薦"}
NON_VIDEO_PATHS = ("/mypage","/recommend","/ranking","/news","/login","/channel/","/banned","/tag/")
NOISE_PHRASES = ( "登録者", "YouTuber", "指摘", "炎上", "運営", "非認可", "注意喚起", "チャンネル登録者", "推薦", "マイページ" )

def now_utc_iso(): return datetime.now(timezone.utc).isoformat(timespec="seconds")

def _clean(s:str)->str:
    if not s: return ""
    return " ".join(s.split()).strip()

def _parse_date_text(t:str):
    patterns = [
        r"(20\d{2})[-年／\.](\d{1,2})[-月／\.](\d{1,2})",
        r"(\d{4})年(\d{1,2})月(\d{1,2})日",
        r"(\d{4})/(\d{1,2})/(\d{1,2})",
        r"(\d{4})-(\d{1,2})-(\d{1,2})",
    ]
    for pattern in patterns:
        m = re.search(pattern, t)
        if m:
            y, mo, d = map(int, m.groups())
            if 2020 <= y <= 2030 and 1 <= mo <= 12 and 1 <= d <= 31:
                return f"{y:04d}-{mo:02d}-{d:02d}"
    return None

def _canon_url(href:str)->str:
    if not href: return ""
    href=href.split("#")[0]
    return href if href.startswith("http") else urljoin(BASE, href)

def _a_to_url(a):
    if a is None: return None
    for key in ("href","data-href","data-url","data-video","data-clipboard-text"):
        v=a.get(key)
        if v and v!="#": return _canon_url(v)
    return None

def _looks_like_video_url(u:str)->bool:
    low=(u or "").lower()
    if any(p in low for p in NON_VIDEO_PATHS): return False
    return ("youtube.com" in low) or ("youtu.be" in low) or ("/watch" in low) or ("/shorts/" in low) or ("/video/" in low)

def _clean_title_candidate(t:str)->str:
    t=_clean(t)
    for w in NON_VIDEO_WORDS:
        if w in t: return ""
    if len(t)<5 or len(t)>120: return ""
    if ("登録者" in t and "YouTuber" in t): return ""
    return t

def _title_score(t:str)->int:
    L=len(t); base = 100 - abs(40-L)
    if "#shorts" in t or "ショート" in t: base += 5
    if "【" in t or "】" in t: base += 3
    return base

def collect_detail_links_on_page_with_ban_dates(html):
    soup=BeautifulSoup(html,"lxml")
    results=[]
    cards = soup.select("h2")
    if not cards:
        cards = soup.select("article, .media, .c-card, .l-list li, .l-grid li, .row")
    if not cards:
        page_text=soup.get_text(" ", strip=True)
        common_date=_parse_date_text(page_text)
        for a in soup.select('a[href^="/channel/"]'):
            path=urlparse(a.get("href","")).path
            if re.fullmatch(r"/channel/\d+/?", path):
                results.append((urljoin(BASE,path).rstrip("/"), common_date))
        return results
    for card in cards:
        context_text = ""
        prev_sibling = card.previous_sibling
        while prev_sibling and len(context_text) < 500:
            if hasattr(prev_sibling, 'get_text'):
                context_text = prev_sibling.get_text(" ", strip=True) + " " + context_text
            elif isinstance(prev_sibling, str):
                context_text = prev_sibling.strip() + " " + context_text
            prev_sibling = prev_sibling.previous_sibling
        context_text += " " + card.get_text(" ", strip=True)
        next_sibling = card.next_sibling
        while next_sibling and len(context_text) < 1000:
            if hasattr(next_sibling, 'get_text'):
                context_text += " " + next_sibling.get_text(" ", strip=True)
            elif isinstance(next_sibling, str):
                context_text += " " + next_sibling.strip()
            next_sibling = next_sibling.next_sibling
        bd=_parse_date_text(context_text)
        links_found = []
        for a in card.select('a[href^="/channel/"]'):
            path=urlparse(a.get("href","")).path
            if re.fullmatch(r"/channel/\d+/?", path):
                links_found.append(path)
        parent = card.parent
        if parent:
            for a in parent.select('a[href^="/channel/"]'):
                path=urlparse(a.get("href","")).path
                if re.fullmatch(r"/channel/\d+/?", path):
                    links_found.append(path)
        for path in set(links_found):
            results.append((urljoin(BASE,path).rstrip("/"), bd))
    uniq={}
    for u,d in results: uniq[u]=d or uniq.get(u)
    return [(u,uniq[u]) for u in uniq.keys()]

def parse_detail_page(html, detail_url):
    soup=BeautifulSoup(html,"lxml"); text=soup.get_text("\n",strip=True)
    m=re.search(r"/channel/(\d+)/?", urlparse(detail_url).path); channel_id=int(m.group(1)) if m else None
    title=None
    node=soup.select_one('meta[property="og:title"]')
    if node: title=node.get("content")
    if not title:
        node=soup.find(["h1","h2"])
        if node: title=node.get_text(strip=True)
    if not title:
        node=soup.find("title")
        if node: title=node.get_text(strip=True)
    def _clean_title(t):
        import re
        t=(t or "").strip()
        t=re.sub(r"\s*[-|｜]\s*ユーチュラ.*$","",t)
        return t if t and t!="チャンネルの詳細" and not re.fullmatch(r"\d+", t) else None
    title=_clean_title(title)

    is_suspended=int(("現在停止" in text) or ("アカウント停止" in text) or ("BAN" in text))

    ban_date = None
    for pattern in [
        r"(\d{4})年(\d{1,2})月(\d{1,2})日.*?BANされました",
        r"(\d{4})年(\d{1,2})月(\d{1,2})日.*?BAN",
        r"(\d{4})年(\d{1,2})月(\d{1,2})日.*?停止",
        r"(\d{4})年(\d{1,2})月(\d{1,2})日.*?削除",
        r"(\d{4})/(\d{1,2})/(\d{1,2}).*?BAN",
        r"(\d{4})-(\d{1,2})-(\d{1,2}).*?BAN"
    ]:
        m=re.search(pattern, text, re.S)
        if m:
            y,mo,d=map(int,m.groups()); 
            ban_date=f"{y:04d}-{mo:02d}-{d:02d}"
            break
    if not ban_date:
        ban_date=_parse_date_text(text)

    def jpnum_to_int(s:str):
        if not s: return None
        t=re.sub(r"[,\s]","",s); t=re.sub(r"(人|回|本)$","",t)
        if t in ("","0"): return 0
        tot=0
        m=re.search(r"(\d+)億",t); tot+=int(m.group(1))*100_000_000 if m else 0
        m=re.search(r"(\d+)万",t); tot+=int(m.group(1))*10_000 if m else 0
        tail=re.sub(r".*[億万]","",t); 
        if tail.isdigit(): tot+=int(tail)
        return tot
    def safe_int(x):
        if x is None: return None
        s=str(x).strip().replace(",","")
        return int(s) if s.isdigit() else None

    subs=views=videos=None
    m=re.search(r"チャンネル登録者\s*([0-9\s,万億]+)", text); subs=jpnum_to_int(m.group(1)) if m else None
    m=re.search(r"動画再生回数\s*([0-9\s,万億]+)回?", text); views=jpnum_to_int(m.group(1)+"回") if m else None
    m=re.search(r"動画数\s*([0-9,]+)\s*本", text); videos=safe_int(m.group(1)) if m else None

    opened_on=None
    m=re.search(r"チャンネル開設日\s*(\d{4})年(\d{1,2})月(\d{1,2})日", text)
    if m: y,mo,d=map(int,m.groups()); opened_on=f"{y:04d}-{mo:02d}-{d:02d}"

    raw=[]
    for a in soup.select('a[href^="/tag/"]'):
        t=(a.get_text() or "").strip()
        if not t or t in {"タグ","Yutura","ユーチュラ"}: continue
        raw.append(t)
    from collections import OrderedDict
    tags="|".join(OrderedDict.fromkeys(raw))

    return {"channel_id":channel_id,"detail_url":detail_url.rstrip("/"),"ban_date":ban_date,
            "channel_name":title,"is_suspended":is_suspended,
            "subs":subs,"views":views,"videos":videos,"opened_on":opened_on,
            "tags":tags,"auto_tags":None,"page_text":text,"shorts_ratio":"-","scraped_at":now_utc_iso(),"debug_note":None,"ban_reason_ai":None}

def build_latest_url(detail_url:str)->str:
    return detail_url.rstrip("/") + "/latest/"

def parse_latest_videos(html:str, detail_url:str, channel_id:int, max_items=3, year_hint=None):
    soup=BeautifulSoup(html,"lxml")
    def _looks_like_video_url(u:str)->bool:
        low=(u or "").lower()
        if any(p in low for p in ("/mypage","/recommend","/ranking","/news","/login","/channel/","/banned","/tag/")): return False
        return ("youtube.com" in low) or ("youtu.be" in low) or ("/watch" in low) or ("/shorts/" in low) or ("/video/" in low)

    rows, seen, shorts = [], set(), 0
    anchors = [a for a in soup.find_all("a", href=True) if _looks_like_video_url(a.get("href",""))]
    for a in anchors:
        url = a.get("href")
        if not url or url in seen: continue
        title=a.get("title") or a.get_text(" ", strip=True)
        title=title[:200] if title else ""
        if not title: continue
        row_tx = a.get_text(" ", strip=True)

        import re
        views_tx=None
        m=re.search(r"([0-9,\s万億]+)\s*回", row_tx); views_tx=(m.group(1)+"回") if m else None
        def jpnum_to_int(s:str):
            if not s: return None
            t=re.sub(r"[,\s]","",s); t=re.sub(r"(人|回|本)$","",t)
            if t in ("","0"): return 0
            tot=0
            m=re.search(r"(\d+)億",t); tot+=int(m.group(1))*100_000_000 if m else 0
            m=re.search(r"(\d+)万",t); tot+=int(m.group(1))*10_000 if m else 0
            tail=re.sub(r".*[億万]","",t); 
            if tail.isdigit(): tot+=int(tail)
            return tot
        views=jpnum_to_int(views_tx) if views_tx else None

        pub_tx=pub_iso=None
        m=re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日\s*(\d{1,2}):(\d{2})", row_tx)
        if m:
            y,mo,d,H,M=map(int,m.groups())
            pub_tx=f"{y}年{mo}月{d}日 {H:02d}:{M:02d}"
            pub_iso=f"{y:04d}-{mo:02d}-{d:02d}T{H:02d}:{M:02d}:00"
        else:
            m2=re.search(r"(\d{1,2})月(\d{1,2})日\s*(\d{1,2}):(\d{2})", row_tx)
            if m2:
                mo,d,H,M=map(int,m2.groups())
                y = int((year_hint or datetime.now().strftime("%Y"))[:4])
                pub_tx=f"{y}年{mo}月{d}日 {H:02d}:{M:02d}"
                pub_iso=f"{y:04d}-{mo:02d}-{d:02d}T{H:02d}:{M:02d}:00"

        likes=None
        m=re.search(r"(いいね|高評価)\s*([0-9,]+)", row_tx)
        if m:
            likes=int(m.group(2).replace(",",""))

        if "/shorts/" in url.lower() or re.search(r"(Shorts|ショート|#shorts)", title, re.I):
            shorts+=1

        rows.append({
            "channel_id":channel_id,"detail_url":detail_url.rstrip("/"),
            "latest_url":build_latest_url(detail_url),
            "video_title":title,"video_url":url,
            "video_views":views,"video_views_tx":views_tx,
            "video_likes":likes,"published_at":pub_iso,"published_tx":pub_tx,
            "scraped_at":datetime.now(timezone.utc).isoformat(timespec="seconds"),
        })
        seen.add(url)
        if len(rows)>=max_items: break

    ratio=f"{round(100*shorts/max(1,len(rows)))}%" if rows else "-"
    return rows, ratio

def scrape_ban_pages(db: Database, start_page:int=1, max_pages:int=50, videos_per_channel:int=3,
                     cookies_txt:str|None=None, cookies_json:str|None=None, extra_cookie_header:str|None=None,
                     retry:int=5, request_wait:float=0.45, page_wait:float=1.2, cooldown_429:int=90, debug:bool=False):
    if debug:
        logging.getLogger().setLevel(logging.DEBUG)

    s=build_session(use_cloudscraper=True, cookies_txt=cookies_txt, cookies_json=cookies_json, extra_cookie_header=extra_cookie_header)

    page=max(1,start_page); pages_done=0; seen=set()
    while True:
        url=LIST_URL if page==1 else f"{LIST_URL}?p={page}"
        logger.info(f"fetch list: {url}")
        html=fetch_html(s,url,retry=retry,base_wait=request_wait,cooldown_429=cooldown_429)

        pairs=collect_detail_links_on_page_with_ban_dates(html)
        if not pairs:
            logger.warning(f"[{page}] linkなし → 終了"); break
        logger.info(f"[{page}] {len(pairs)} channels")

        for du, ban_date_list in pairs:
            du=du.rstrip("/")
            if du in seen: continue
            seen.add(du)
            try:
                dhtml=fetch_html(s,du,retry=retry,base_wait=request_wait,cooldown_429=cooldown_429)
                ch=parse_detail_page(dhtml,du); ch["list_page"]=page
                ch["ban_date"]=ban_date_list or ch["ban_date"]

                vids,ratio=([], "-"); debug_note=None
                latest_titles=[]
                if videos_per_channel>0 and ch.get("channel_id"):
                    try:
                        lurl=build_latest_url(du)
                        lhtml=fetch_html(s,lurl,retry=retry,base_wait=request_wait,cooldown_429=cooldown_429)
                        vids,ratio=parse_latest_videos(lhtml,du,ch["channel_id"],
                                                       max_items=min(max(2,videos_per_channel),3),
                                                       year_hint=ch.get("ban_date"))
                    except Exception as e:
                        logger.debug(f"latest fetch fail: {e}")
                    if len(vids)==0:
                        debug_note="no_videos: latest selectors matched 0 links"

                ch["shorts_ratio"]=ratio
                ch["debug_note"]=debug_note

                # upsert channel
                db.execute("""
                INSERT INTO channels
                  (channel_id, detail_url, list_page, ban_date, channel_name, is_suspended,
                   subs, views, videos, opened_on, tags, auto_tags, page_text, shorts_ratio, scraped_at, debug_note, ban_reason_ai)
                VALUES
                  (:channel_id,:detail_url,:list_page,:ban_date,:channel_name,:is_suspended,
                   :subs,:views,:videos,:opened_on,:tags,:auto_tags,:page_text,:shorts_ratio,:scraped_at,:debug_note,:ban_reason_ai)
                ON CONFLICT(channel_id) DO UPDATE SET
                  detail_url=COALESCE(excluded.detail_url,detail_url),
                  list_page=COALESCE(excluded.list_page,list_page),
                  ban_date=COALESCE(excluded.ban_date,ban_date),
                  channel_name=CASE WHEN excluded.channel_name IS NULL OR excluded.channel_name='' THEN channel_name
                                    WHEN excluded.channel_name='チャンネルの詳細' THEN channel_name
                                    ELSE excluded.channel_name END,
                  is_suspended=COALESCE(excluded.is_suspended,is_suspended),
                  subs=COALESCE(excluded.subs,subs), views=COALESCE(excluded.views,views), videos=COALESCE(excluded.videos,videos),
                  opened_on=COALESCE(excluded.opened_on,opened_on),
                  tags=CASE WHEN tags IS NULL OR tags='' THEN excluded.tags
                            WHEN excluded.tags IS NULL OR excluded.tags=='' THEN tags
                            ELSE tags||'|'||excluded.tags END,
                  auto_tags=COALESCE(excluded.auto_tags,auto_tags),
                  page_text=COALESCE(excluded.page_text,page_text),
                  shorts_ratio=COALESCE(excluded.shorts_ratio,shorts_ratio),
                  scraped_at=COALESCE(excluded.scraped_at,scraped_at),
                  debug_note=COALESCE(excluded.debug_note,debug_note),
                  ban_reason_ai=COALESCE(excluded.ban_reason_ai,ban_reason_ai);
                """, ch)

                for i,v in enumerate(vids,1):
                    v["video_rank"]=i
                    db.execute("""
                    INSERT INTO videos
                      (channel_id, detail_url, latest_url, video_rank, video_title, video_url,
                       video_views, video_views_tx, video_likes, published_at, published_tx, scraped_at)
                    VALUES
                      (:channel_id,:detail_url,:latest_url,:video_rank,:video_title,:video_url,
                       :video_views,:video_views_tx,:video_likes,:published_at,:published_tx,:scraped_at)
                    ON CONFLICT(channel_id, video_url) DO UPDATE SET
                      video_rank=COALESCE(excluded.video_rank,video_rank),
                      video_title=COALESCE(excluded.video_title,video_title),
                      video_views=COALESCE(excluded.video_views,video_views),
                      video_views_tx=COALESCE(excluded.video_views_tx,video_views_tx),
                      video_likes=COALESCE(excluded.video_likes,video_likes),
                      published_at=COALESCE(excluded.published_at,published_at),
                      published_tx=COALESCE(excluded.published_tx,published_tx),
                      scraped_at=COALESCE(excluded.scraped_at,scraped_at);
                    """, v)

                if request_wait>0: time.sleep(request_wait)
            except Exception as e:
                logger.error(f"ERR: {du} {e}"); time.sleep(0.3)

        pages_done+=1; page+=1
        if max_pages>0 and pages_done>=max_pages:
            logger.info("max-pages 到達 → 終了"); break
        if page_wait>0: time.sleep(page_wait)
    logger.info("Done.")
