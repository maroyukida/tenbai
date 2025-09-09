# -*- coding: utf-8 -*-
from flask import Flask, render_template, request, jsonify, url_for
import json
import sqlite3
import csv
import os
from urllib.parse import quote_plus
import time
from datetime import datetime, timezone, timedelta
from ..config import Config
import traceback


def create_app(cfg: Config | None = None) -> Flask:
    cfg = cfg or Config()
    app = Flask(__name__, template_folder="../templates", static_folder="../static")
    app.secret_key = cfg.secret_key
    app.config['TEMPLATES_AUTO_RELOAD'] = True
    app.config['ASSET_VER'] = int(time.time())

    # Jinja filter: ISO8601(Z/offset/naive) -> JST string
    def to_jst(val: object, fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
        if not val:
            return "-"
        try:
            s = str(val)
            # Accept ISO with 'Z' or '+/-HH:MM' or naive
            if "Z" in s:
                s = s.replace("Z", "+00:00")
            dt = datetime.fromisoformat(s)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            jst = dt.astimezone(timezone(timedelta(hours=9)))
            return jst.strftime(fmt)
        except Exception:
            return str(val)

    app.jinja_env.filters["to_jst"] = to_jst
    app.jinja_env.filters["urlq"] = lambda s: quote_plus(str(s)) if s is not None else ""

    # Formatting helpers for toC UI
    def _fmt_int(x):
        try:
            return f"{int(float(x)):,}"
        except Exception:
            return x

    def _fmt_money(x):
        try:
            return f"¥{int(round(float(x))):,}"
        except Exception:
            return x

    def _fmt_float(x, nd=2):
        try:
            return f"{float(x):.{nd}f}"
        except Exception:
            return x

    def _fmt_pct(x, nd=0):
        try:
            return f"{float(x)*100:.{nd}f}%"
        except Exception:
            return x

    def _score_cls(x):
        try:
            v = float(x)
        except Exception:
            return "score-low"
        return "score-high" if v >= 0.8 else ("score-mid" if v >= 0.6 else "score-low")

    def _img_label(d):
        try:
            v = int(d)
        except Exception:
            return "-"
        if v <= 6:
            return "強一致"
        if v <= 12:
            return "弱一致"
        return "-"

    app.jinja_env.filters["fmt_int"] = _fmt_int
    app.jinja_env.filters["fmt_money"] = _fmt_money
    app.jinja_env.filters["fmt_float"] = _fmt_float
    app.jinja_env.filters["fmt_pct"] = _fmt_pct
    app.jinja_env.filters["score_cls"] = _score_cls
    app.jinja_env.filters["img_label"] = _img_label

    # Category label mapping (EN -> JA) used in templates
    _CAT_JA_MAP: dict[str, str] = {
        # YouTube-like general categories
        "Music": "音楽",
        "Gaming": "ゲーム",
        "Entertainment": "エンタメ",
        "People & Blogs": "ブログ・日常",
        "News & Politics": "ニュース・政治",
        "Sports": "スポーツ",
        "Education": "教育",
        "Tech": "テクノロジー",
        "Science & Technology": "科学・技術",
        "Film & Animation": "映画・アニメ",
        "Autos & Vehicles": "自動車・乗り物",
        "Pets & Animals": "ペット・動物",
        "Howto & Style": "ハウツー・スタイル",
        "Travel & Events": "旅行・イベント",
        "Comedy": "コメディ",
        "Nonprofits & Activism": "非営利・社会運動",

        # Custom genre labels used by our categorizer (vcats)
        "Kirinuki": "切り抜き",
        "Yukkuri": "ゆっくり",
        "Nanj": "なんJ",
        "Sukatto": "スカッと",
        "ASMR": "ASMR",
        "2ch/5ch": "2ch/5ch",
        "Anime & Manga": "アニメ・マンガ",
        "Idol": "アイドル",
        "K-POP": "K-POP",
        "Food & Cooking": "料理・グルメ",
        "Beauty & Makeup": "美容・メイク",
        "Fitness": "フィットネス",
        "DIY & Crafts": "DIY・クラフト",
        "Outdoors & Camping": "アウトドア・キャンプ",
        "Fishing": "釣り",
        "Cars & Bikes": "車・バイク",
    }

    def _cat_ja(name: object) -> str:
        try:
            if name is None:
                return "-"
            s = str(name)
            return _CAT_JA_MAP.get(s, s)
        except Exception:
            return str(name) if name is not None else "-"

    app.jinja_env.filters["cat_ja"] = _cat_ja
    # Override broken mojibake label mapping with proper Japanese labels
    def _img_label(d):
        try:
            v = int(d)
        except Exception:
            return "-"
        if v <= 6:
            return "近い"
        if v <= 12:
            return "やや近い"
        return "-"
    app.jinja_env.filters["img_label"] = _img_label

    @app.context_processor
    def inject_globals():
        return {"asset_ver": app.config.get('ASSET_VER', 1)}

    # Simple CORS for /resale JSON endpoints (for Next.js on another port)
    @app.after_request
    def add_cors(resp):
        try:
            p = request.path or ""
            if p.startswith("/resale/") and (p.endswith(".json") or p == "/resale/debug"):
                resp.headers['Access-Control-Allow-Origin'] = '*'
                resp.headers['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
                resp.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        except Exception:
            pass
        return resp
    def fmt_num(val: object) -> str:
        try:
            if val is None:
                return "-"
            n = int(float(val))
            return f"{n:,}"
        except Exception:
            try:
                return f"{int(val):,}"
            except Exception:
                return str(val)
    app.jinja_env.filters["num"] = fmt_num

    # Force UTF-8 for HTML responses
    @app.after_request
    def _force_utf8(resp):
        try:
            ctype = resp.headers.get("Content-Type","")
            if ctype.startswith("text/html") and "charset=" not in ctype:
                resp.headers["Content-Type"] = "text/html; charset=utf-8"
        except Exception:
            pass
        return resp

    def _rss_con():
        con = sqlite3.connect(cfg.rss_db_path, timeout=60, check_same_thread=False)
        con.row_factory = sqlite3.Row
        # Improve concurrency and reduce intermittent "database is locked"
        try:
            con.execute("pragma journal_mode=WAL")
            con.execute("pragma synchronous=NORMAL")
            con.execute("pragma temp_store=MEMORY")
            con.execute("pragma busy_timeout=60000")
        except Exception:
            pass
        return con

    def _rss_con_ro():
        try:
            # Read-only snapshot; avoids writer locks entirely
            uri = f"file:{cfg.rss_db_path}?mode=ro"
            con = sqlite3.connect(uri, uri=True, timeout=60, check_same_thread=False)
        except Exception:
            # Fallback to normal connection if URI mode not supported
            con = sqlite3.connect(cfg.rss_db_path, timeout=60, check_same_thread=False)
        con.row_factory = sqlite3.Row
        try:
            con.execute("pragma journal_mode=WAL")
            con.execute("pragma synchronous=NORMAL")
            con.execute("pragma temp_store=MEMORY")
            con.execute("pragma busy_timeout=60000")
        except Exception:
            pass
        return con

    def _has_col(cur: sqlite3.Cursor, table: str, col: str) -> bool:
        try:
            cols = {r[1] for r in cur.execute(f"pragma table_info({table})").fetchall()}
            return col in cols
        except Exception:
            return False

    def _has_table(cur: sqlite3.Cursor, table: str) -> bool:
        try:
            r = cur.execute("select 1 from sqlite_master where type='table' and name=? limit 1", (table,)).fetchone()
            return bool(r)
        except Exception:
            return False

    def _ensure_watchlist(cur: sqlite3.Cursor) -> None:
        try:
            cur.execute(
                """
                create table if not exists rss_watchlist(
                  channel_id text primary key,
                  handle text,
                  title text,
                  added_at text
                )
                """
            )
        except Exception:
            pass

    # simple CSV readers for resale views
    def _read_csv_rows(path: str) -> list[dict]:
        try:
            if not os.path.exists(path):
                return []
            with open(path, "r", encoding="utf-8") as f:
                r = csv.DictReader(f)
                return [dict(row) for row in r]
        except UnicodeDecodeError:
            with open(path, "r", encoding="utf-8-sig") as f:
                r = csv.DictReader(f)
                return [dict(row) for row in r]
        except Exception:
            return []

    @app.errorhandler(Exception)
    def _on_error(exc: Exception):
        try:
            os.makedirs('logs', exist_ok=True)
            with open(os.path.join('logs', 'web_errors.log'), 'a', encoding='utf-8') as f:
                f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {request.path}\n")
                f.write(traceback.format_exc())
                f.write("\n")
        except Exception:
            pass
        return render_template('error.html', message='内部サーバーエラー'), 500

    @app.route("/health")
    def health():
        try:
            con = _rss_con(); cur = con.cursor()
            n = cur.execute("select count(*) from trending_ranks").fetchone()[0]
        except Exception:
            n = 0
        return jsonify({"ok": True, "trending": int(n)}), 200

    @app.route("/trending.json")
    def trending_json():
        q_type = request.args.get("type")
        q_cat = request.args.get("category")
        q_vcat = request.args.get("vcat")
        sort = request.args.get("sort", "score")
        page = int(request.args.get("page", 1))
        per = int(request.args.get("per", request.args.get("limit", 50)))
        offset = max(0, (page - 1) * per)
        con = _rss_con_ro(); cur = con.cursor()
        has_vc = _has_table(cur, 'video_categories')
        where = []
        params = []
        if q_type == 'short':
            where.append("is_short=1")
        elif q_type == 'long':
            where.append("is_short=0")
        if q_cat:
            where.append("category_name=?")
            params.append(q_cat)
        join_vc = " left join video_categories vc on vc.video_id=trending_ranks.video_id " if has_vc else ""
        if q_vcat:
            # fallback: vc.primary_label が無い場合は YouTube の category_name を利用
            if has_vc:
                where.append("coalesce(vc.primary_label, trending_ranks.category_name)=?")
            else:
                where.append("trending_ranks.category_name=?")
            params.append(q_vcat)
        wsql = (" where " + " and ".join(where)) if where else ""
        total = cur.execute(f"select count(*) from trending_ranks{join_vc}{wsql}", tuple(params)).fetchone()[0]
        vcat_expr = "coalesce(vc.primary_label, trending_ranks.category_name)" if has_vc else "trending_ranks.category_name"
        select_cols = f"trending_ranks.video_id, channel_id, title, thumb_hq, published_at, category_name, is_short, score, d1h, d3h, d6h, likes_per_hour, current_views, {vcat_expr} as vcat"
        if _has_col(cur, 'trending_ranks', 'channel_title'):
            select_cols = f"trending_ranks.video_id, channel_id, channel_title, title, thumb_hq, published_at, category_name, is_short, score, d1h, d3h, d6h, likes_per_hour, current_views, {vcat_expr} as vcat"
        order = {
            "score": "score desc",
            "likes": "coalesce(likes_per_hour,0) desc",
            "views": "coalesce(current_views,0) desc",
            "published": "published_at desc",
        }.get((sort or "score").lower(), "score desc")
        rows = cur.execute(
            f"select {select_cols} from trending_ranks{join_vc}{wsql} order by {order} limit ? offset ?",
            (*params, per, offset),
        ).fetchall()
        data = []
        for r in rows:
            d = dict(r)
            ch = d.get("channel_id")
            if ch:
                d["channel_url"] = f"https://www.youtube.com/channel/{ch}"
            data.append(d)
        # vc.primary_label が無い場合は category_name を合流した候補を提示
        # Build vcats safely (video_categories may be missing on fresh DB)
        vcats = []
        try:
            if _has_table(cur, 'video_categories'):
                vcats = [
                    x[0]
                    for x in cur.execute(
                        "select distinct coalesce(vc.primary_label, tr.category_name) as vcat from trending_ranks tr left join video_categories vc on vc.video_id=tr.video_id where vcat is not null order by vcat"
                    ).fetchall()
                ]
            else:
                vcats = [x[0] for x in cur.execute("select distinct category_name from trending_ranks where category_name is not null order by category_name").fetchall()]
        except Exception:
            vcats = []
        return jsonify({"items": data, "page": page, "per": per, "total": int(total), "vcats": vcats})

    @app.route("/trending")
    def trending():
        con = _rss_con_ro(); cur = con.cursor()
        # デフォルトは見やすい List 表示にする
        view = request.args.get("view", "list")
        if view == "list":
            q_type = request.args.get("type")
            q_cat = request.args.get("category")
            q_vcat = request.args.get("vcat")
            sort = request.args.get("sort", "score")
            page = int(request.args.get("page", 1))
            per = int(request.args.get("per", 50))
            offset = max(0, (page - 1) * per)
            where = []
            params = []
            if q_type == 'short':
                where.append("is_short=1")
            elif q_type == 'long':
                where.append("is_short=0")
            if q_cat:
                where.append("category_name=?")
                params.append(q_cat)
            has_vc = _has_table(cur, 'video_categories')
            join_vc = " left join video_categories vc on vc.video_id=trending_ranks.video_id " if has_vc else ""
            if q_vcat:
                if has_vc:
                    where.append("coalesce(vc.primary_label, trending_ranks.category_name)=?")
                else:
                    where.append("trending_ranks.category_name=?")
                params.append(q_vcat)
            wsql = (" where " + " and ".join(where)) if where else ""
            total = cur.execute(f"select count(*) from trending_ranks{join_vc}{wsql}", tuple(params)).fetchone()[0]
            vcat_expr = "coalesce(vc.primary_label, trending_ranks.category_name)" if has_vc else "trending_ranks.category_name"
            select_cols = f"trending_ranks.video_id, channel_id, title, thumb_hq, published_at, category_name, is_short, score, d1h, d3h, d6h, likes_per_hour, current_views, {vcat_expr} as vcat"
            if _has_col(cur, 'trending_ranks', 'channel_title'):
                select_cols = f"trending_ranks.video_id, channel_id, channel_title, title, thumb_hq, published_at, category_name, is_short, score, d1h, d3h, d6h, likes_per_hour, current_views, {vcat_expr} as vcat"
            order = {
                "score": "score desc",
                "likes": "coalesce(likes_per_hour,0) desc",
                "views": "coalesce(current_views,0) desc",
                "published": "published_at desc",
            }.get((sort or "score").lower(), "score desc")
            rows = cur.execute(
                f"select {select_cols} from trending_ranks{join_vc}{wsql} order by {order} limit ? offset ?",
                (*params, per, offset),
            ).fetchall()
            items = [dict(r) for r in rows]
            cats = [r[0] for r in cur.execute("select distinct category_name from trending_ranks where category_name is not null order by category_name").fetchall()]
            try:
                if _has_table(cur, 'video_categories'):
                    vcats = [
                        x[0]
                        for x in cur.execute(
                            "select distinct coalesce(vc.primary_label, tr.category_name) as vcat from trending_ranks tr left join video_categories vc on vc.video_id=tr.video_id where vcat is not null order by vcat"
                        ).fetchall()
                    ]
                else:
                    vcats = [r[0] for r in cur.execute("select distinct category_name from trending_ranks where category_name is not null order by category_name").fetchall()]
            except Exception:
                vcats = []
            return render_template("trending_list.html", items=items, page=page, per=per, total=total, cats=cats, vcats=vcats, q_type=q_type or "", q_cat=q_cat or "", q_vcat=q_vcat or "", sort=(sort or "score"))
        # grid
        q_type = request.args.get("type")
        q_cat = request.args.get("category")
        cats = [r[0] for r in cur.execute("select distinct category_name from trending_ranks where category_name is not null order by category_name").fetchall()]
        if q_cat:
            cats = [q_cat]
        tdefs = [(1, "Shorts"), (0, "Longs")]
        if q_type == 'short':
            tdefs = [(1, "Shorts")]
        elif q_type == 'long':
            tdefs = [(0, "Longs")]
        groups = []
        for is_short, label in tdefs:
            for c in cats:
                rows = cur.execute(
                    "select video_id, title, thumb_hq, score, current_views from trending_ranks where is_short=? and category_name=? order by score desc limit 12",
                    (is_short, c),
                ).fetchall()
                if not rows:
                    continue
                groups.append({
                    "header": f"{label} × {c}",
                    "items": [dict(r) for r in rows]
                })
        return render_template("trending.html", groups=groups, cats=cats)

    # day ranks (channels)
    @app.route("/day-channels.json")
    def day_channels_json():
        con = _rss_con(); cur = con.cursor()
        date = request.args.get("date")
        if not date:
            r = cur.execute("select date from channel_day_ranks order by date desc limit 1").fetchone()
            date = r[0] if r else None
        page = int(request.args.get("page", 1)); per = int(request.args.get("per", 50))
        offset = max(0, (page-1)*per)
        if not date:
            return jsonify({"items": [], "page": page, "per": per, "total": 0})
        total = cur.execute("select count(*) from channel_day_ranks where date=?", (date,)).fetchone()[0]
        rows = cur.execute(
            "select channel_id, title, delta_views, delta_subs, score from channel_day_ranks where date=? order by score desc limit ? offset ?",
            (date, per, offset),
        ).fetchall()
        return jsonify({"items": [dict(r) for r in rows], "page": page, "per": per, "total": int(total), "date": date})

    @app.route("/day-channels")
    def day_channels():
        con = _rss_con(); cur = con.cursor()
        date = request.args.get("date")
        if not date:
            r = cur.execute("select date from channel_day_ranks order by date desc limit 1").fetchone()
            date = r[0] if r else None
        page = int(request.args.get("page", 1)); per = int(request.args.get("per", 50))
        offset = max(0, (page-1)*per)
        rows = cur.execute(
            "select channel_id, title, delta_views, delta_subs, score from channel_day_ranks where date=? order by score desc limit ? offset ?",
            (date, per, offset),
        ).fetchall()
        items = [dict(r) for r in rows]
        total = cur.execute("select count(*) from channel_day_ranks where date=?", (date,)).fetchone()[0]
        return render_template("day_channels_list.html", items=items, date=date or '-', page=page, per=per, total=total)

    # all videos (from rss_videos) with pagination
    @app.route("/videos.json")
    def videos_json():
        con = _rss_con(); cur = con.cursor()
        page = int(request.args.get("page", 1))
        per = int(request.args.get("per", 50))
        q = request.args.get("q")
        q_vcat = request.args.get("vcat")
        sort = request.args.get("sort", "discovered")  # discovered|published
        offset = max(0, (page - 1) * per)
        where = []
        params = []
        if q:
            where.append("(v.title like ?)")
            params.append(f"%{q}%")
        join_vc = " left join video_categories vc on vc.video_id=v.video_id "
        if q_vcat:
            where.append("vc.primary_label=?")
            params.append(q_vcat)
        wsql = (" where " + " and ".join(where)) if where else ""
        order = "coalesce(d.discovered_at, v.published_at) desc" if sort == "discovered" else "v.published_at desc"
        total = cur.execute(f"select count(*) from rss_videos v left join rss_videos_discovered d on d.video_id=v.video_id{join_vc}{wsql}", tuple(params)).fetchone()[0]
        rows = cur.execute(
            f"select v.video_id, v.channel_id, v.title, v.thumb_hq, v.published_at, d.discovered_at, vc.primary_label as vcat from rss_videos v left join rss_videos_discovered d on d.video_id=v.video_id{join_vc}{wsql} order by {order} limit ? offset ?",
            (*params, per, offset),
        ).fetchall()
        items = []
        for r in rows:
            d = dict(r)
            ch = d.get("channel_id")
            if ch:
                d["channel_url"] = f"https://www.youtube.com/channel/{ch}"
            d["watch_url"] = f"https://www.youtube.com/watch?v={d.get('video_id')}"
            items.append(d)
        try:
            if _has_table(cur, 'video_categories'):
                vcats = [x[0] for x in cur.execute("select distinct primary_label from video_categories where primary_label is not null order by primary_label").fetchall()]
            else:
                vcats = []
        except Exception:
            vcats = []
        return jsonify({"items": items, "page": page, "per": per, "total": int(total), "vcats": vcats})

    @app.route("/videos")
    def videos():
        con = _rss_con(); cur = con.cursor()
        page = int(request.args.get("page", 1))
        per = int(request.args.get("per", 50))
        q = request.args.get("q", "")
        q_vcat = request.args.get("vcat")
        sort = request.args.get("sort", "discovered")
        offset = max(0, (page - 1) * per)
        where = []
        params = []
        if q:
            where.append("(v.title like ?)")
            params.append(f"%{q}%")
        join_vc = " left join video_categories vc on vc.video_id=v.video_id "
        if q_vcat:
            where.append("vc.primary_label=?")
            params.append(q_vcat)
        wsql = (" where " + " and ".join(where)) if where else ""
        order = "coalesce(d.discovered_at, v.published_at) desc" if sort == "discovered" else "v.published_at desc"
        total = cur.execute(f"select count(*) from rss_videos v left join rss_videos_discovered d on d.video_id=v.video_id{join_vc}{wsql}", tuple(params)).fetchone()[0]
        rows = cur.execute(
            f"select v.video_id, v.channel_id, v.title, v.thumb_hq, v.published_at, d.discovered_at, vc.primary_label as vcat from rss_videos v left join rss_videos_discovered d on d.video_id=v.video_id{join_vc}{wsql} order by {order} limit ? offset ?",
            (*params, per, offset),
        ).fetchall()
        items = [dict(r) for r in rows]
        try:
            if _has_table(cur, 'video_categories'):
                vcats = [x[0] for x in cur.execute("select distinct primary_label from video_categories where primary_label is not null order by primary_label").fetchall()]
            else:
                vcats = []
        except Exception:
            vcats = []
        return render_template("videos_list.html", items=items, page=page, per=per, total=total, q=q, sort=sort, vcats=vcats, q_vcat=q_vcat or "")

    # watchlist-limited videos
    @app.route("/watch-videos.json")
    def watch_videos_json():
        con = _rss_con(); cur = con.cursor()
        _ensure_watchlist(cur)
        page = int(request.args.get("page", 1))
        per = int(request.args.get("per", 50))
        q = request.args.get("q")
        q_vcat = request.args.get("vcat")
        sort = request.args.get("sort", "discovered")  # discovered|published
        offset = max(0, (page - 1) * per)
        where = ["exists (select 1 from rss_watchlist wl where wl.channel_id=v.channel_id)"]
        params: list[object] = []
        if q:
            where.append("(v.title like ?)")
            params.append(f"%{q}%")
        join_vc = " left join video_categories vc on vc.video_id=v.video_id "
        if q_vcat:
            where.append("vc.primary_label=?")
            params.append(q_vcat)
        wsql = (" where " + " and ".join(where)) if where else ""
        order = "coalesce(d.discovered_at, v.published_at) desc" if sort == "discovered" else "v.published_at desc"
        total = cur.execute(f"select count(*) from rss_videos v left join rss_videos_discovered d on d.video_id=v.video_id{join_vc}{wsql}", tuple(params)).fetchone()[0]
        rows = cur.execute(
            f"select v.video_id, v.channel_id, v.title, v.thumb_hq, v.published_at, d.discovered_at, vc.primary_label as vcat from rss_videos v left join rss_videos_discovered d on d.video_id=v.video_id{join_vc}{wsql} order by {order} limit ? offset ?",
            (*params, per, offset),
        ).fetchall()
        items = []
        for r in rows:
            d = dict(r)
            ch = d.get("channel_id")
            if ch:
                d["channel_url"] = f"https://www.youtube.com/channel/{ch}"
            d["watch_url"] = f"https://www.youtube.com/watch?v={d.get('video_id')}"
            items.append(d)
        try:
            if _has_table(cur, 'video_categories'):
                vcats = [x[0] for x in cur.execute("select distinct primary_label from video_categories where primary_label is not null order by primary_label").fetchall()]
            else:
                vcats = []
        except Exception:
            vcats = []
        return jsonify({"items": items, "page": page, "per": per, "total": int(total), "vcats": vcats})

    @app.route("/watch-videos")
    def watch_videos():
        con = _rss_con(); cur = con.cursor()
        _ensure_watchlist(cur)
        page = int(request.args.get("page", 1))
        per = int(request.args.get("per", 50))
        q = request.args.get("q", "")
        q_vcat = request.args.get("vcat")
        sort = request.args.get("sort", "discovered")
        offset = max(0, (page - 1) * per)
        where = ["exists (select 1 from rss_watchlist wl where wl.channel_id=v.channel_id)"]
        params: list[object] = []
        if q:
            where.append("(v.title like ?)")
            params.append(f"%{q}%")
        join_vc = " left join video_categories vc on vc.video_id=v.video_id "
        if q_vcat:
            where.append("vc.primary_label=?")
            params.append(q_vcat)
        wsql = (" where " + " and ".join(where)) if where else ""
        order = "coalesce(d.discovered_at, v.published_at) desc" if sort == "discovered" else "v.published_at desc"
        total = cur.execute(f"select count(*) from rss_videos v left join rss_videos_discovered d on d.video_id=v.video_id{join_vc}{wsql}", tuple(params)).fetchone()[0]
        rows = cur.execute(
            f"select v.video_id, v.channel_id, v.title, v.thumb_hq, v.published_at, d.discovered_at, vc.primary_label as vcat from rss_videos v left join rss_videos_discovered d on d.video_id=v.video_id{join_vc}{wsql} order by {order} limit ? offset ?",
            (*params, per, offset),
        ).fetchall()
        items = [dict(r) for r in rows]
        vcats = [x[0] for x in cur.execute("select distinct primary_label from video_categories where primary_label is not null order by primary_label").fetchall()]
        return render_template("videos_list.html", items=items, page=page, per=per, total=total, q=q, sort=sort, vcats=vcats, q_vcat=q_vcat or "")

    # Resale: seller candidates
    # Base directory for exports (CSV). On serverless (e.g., Vercel), the
    # default exports/ may not exist; fall back to a bundled path.
    exports_base = os.getenv("RESALE_EXPORTS_DIR") or "exports"
    if not os.path.exists(exports_base):
        alt = os.path.abspath(os.path.join(os.path.dirname(__file__), "../published_exports"))
        if os.path.isdir(alt):
            exports_base = alt

    @app.route("/resale")
    def resale_home():
        sellers_path = request.args.get("sellers_path", os.path.join(exports_base, "seller_candidates.csv"))
        verified_path = request.args.get("verified_path", os.path.join(exports_base, "seller_verified.csv"))
        items_path = request.args.get("items_path", os.path.join(exports_base, "seller_verified_items.csv"))

        sellers = _read_csv_rows(sellers_path)
        verified = _read_csv_rows(verified_path)
        items = _read_csv_rows(items_path)

        def _num(r: dict, k: str) -> float:
            try:
                return float(r.get(k, 0) or 0)
            except Exception:
                return 0.0

        top_sellers = sorted(sellers, key=lambda r: (_num(r, "score"), _num(r, "overseas_rate")), reverse=True)[:8]
        filt_items = [r for r in items if _num(r, "est_profit_jpy") > 0 and _num(r, "score") >= 0.7]
        top_items = sorted(filt_items, key=lambda r: (_num(r, "est_profit_jpy"), _num(r, "score")), reverse=True)[:8]

        summary = {
            "sellers_total": len(sellers),
            "verified_total": len(verified),
            "items_total": len(items),
        }
        return render_template(
            "resale_home.html",
            summary=summary,
            top_sellers=top_sellers,
            top_items=top_items,
            sellers_path=sellers_path,
            verified_path=verified_path,
            items_path=items_path,
        )

    @app.route("/resale/top.json")
    def resale_top_json():
        sellers_path = request.args.get("sellers_path", os.path.join(exports_base, "seller_candidates.csv"))
        verified_path = request.args.get("verified_path", os.path.join(exports_base, "seller_verified.csv"))
        items_path = request.args.get("items_path", os.path.join(exports_base, "seller_verified_items.csv"))

        sellers = _read_csv_rows(sellers_path)
        verified = _read_csv_rows(verified_path)
        items = _read_csv_rows(items_path)

        def _num(r: dict, k: str) -> float:
            try:
                return float(r.get(k, 0) or 0)
            except Exception:
                return 0.0

        top_sellers = sorted(sellers, key=lambda r: (_num(r, "score"), _num(r, "overseas_rate")), reverse=True)[:8]
        filt_items = [r for r in items if _num(r, "est_profit_jpy") > 0 and _num(r, "score") >= 0.7]
        top_items = sorted(filt_items, key=lambda r: (_num(r, "est_profit_jpy"), _num(r, "score")), reverse=True)[:8]

        return jsonify({
            "summary": {
                "sellers_total": len(sellers),
                "verified_total": len(verified),
                "items_total": len(items),
            },
            "top_sellers": top_sellers,
            "top_items": top_items,
        })

    @app.route("/resale/debug")
    def resale_debug():
        try:
            tpl_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../templates"))
            static_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../static"))
            css_path = os.path.join(static_dir, "resale.css")
            css_mtime = os.path.getmtime(css_path) if os.path.exists(css_path) else None
        except Exception:
            tpl_dir = static_dir = css_path = "?"
            css_mtime = None
        return jsonify({
            "template_dir": tpl_dir,
            "static_dir": static_dir,
            "css_path": css_path,
            "css_mtime": css_mtime,
            "asset_ver": app.config.get('ASSET_VER'),
        })

    # Resale: seller candidates
    @app.route("/resale/sellers")
    def resale_sellers():
        path = request.args.get("path", os.path.join(exports_base, "seller_candidates.csv"))
        limit = int(request.args.get("limit", 100))
        min_overseas_rate = float(request.args.get("min_overseas_rate", 0) or 0)
        min_overseas = int(request.args.get("min_overseas", 0) or 0)
        sort = request.args.get("sort", "overseas_rate")
        order = request.args.get("order", "desc")
        rows = _read_csv_rows(path)
        def _keep(r: dict) -> bool:
            try:
                if min_overseas_rate and float(r.get("overseas_rate", 0) or 0) < min_overseas_rate:
                    return False
                if min_overseas and int(r.get("overseas_hits", 0) or 0) < min_overseas:
                    return False
                return True
            except Exception:
                return False
        rows = [r for r in rows if _keep(r)]
        # sorting
        def _num(r, k):
            try:
                return float(r.get(k, 0) or 0)
            except Exception:
                return 0.0
        if sort not in {"overseas_rate","score","hit_rate","n_items_sample","title_hits"}:
            sort = "overseas_rate"
        rows.sort(key=lambda r: _num(r, sort), reverse=(order != "asc"))
        items = rows[:limit]
        return render_template("resale_sellers.html", items=items, total=len(rows), path=path, limit=limit)

    @app.route("/resale/sellers.json")
    def resale_sellers_json():
        path = request.args.get("path", "exports/seller_candidates.csv")
        limit = int(request.args.get("limit", 24))
        page = int(request.args.get("page", 1))
        min_overseas_rate = float(request.args.get("min_overseas_rate", 0) or 0)
        min_overseas = int(request.args.get("min_overseas", 0) or 0)
        sort = request.args.get("sort", "overseas_rate")
        order = request.args.get("order", "desc")
        rows = _read_csv_rows(path)
        def _keep(r: dict) -> bool:
            try:
                if min_overseas_rate and float(r.get("overseas_rate", 0) or 0) < min_overseas_rate:
                    return False
                if min_overseas and int(r.get("overseas_hits", 0) or 0) < min_overseas:
                    return False
                return True
            except Exception:
                return False
        rows = [r for r in rows if _keep(r)]
        def _num(r, k):
            try:
                return float(r.get(k, 0) or 0)
            except Exception:
                return 0.0
        if sort not in {"overseas_rate","score","hit_rate","n_items_sample","title_hits"}:
            sort = "overseas_rate"
        rows.sort(key=lambda r: _num(r, sort), reverse=(order != "asc"))
        total = len(rows)
        start = max(0, (page-1)*limit)
        items = rows[start:start+limit]
        return jsonify({"items": items, "total": total, "page": page, "limit": limit})

    # Resale: verified sellers
    @app.route("/resale/verified")
    def resale_verified():
        path = request.args.get("path", os.path.join(exports_base, "seller_verified.csv"))
        limit = int(request.args.get("limit", 100))
        matched_only = request.args.get("matched_only", "0") in ("1", "true", "True")
        min_high = int(request.args.get("min_high", 0) or 0)
        min_avg_profit = float(request.args.get("min_avg_profit", 0) or 0)
        sort = request.args.get("sort", "avg_profit_jpy")
        order = request.args.get("order", "desc")
        rows = _read_csv_rows(path)
        def _keep(r: dict) -> bool:
            try:
                if matched_only and int(r.get("with_ae_candidates", 0) or 0) <= 0:
                    return False
                if min_high and int(r.get("high_score_count", 0) or 0) < min_high:
                    return False
                if min_avg_profit and float(r.get("avg_profit_jpy", 0) or 0) < min_avg_profit:
                    return False
                return True
            except Exception:
                return False
        rows = [r for r in rows if _keep(r)]
        def _num(r, k):
            try:
                return float(r.get(k, 0) or 0)
            except Exception:
                return 0.0
        if sort not in {"avg_profit_jpy","max_score","avg_score","with_ae_candidates","high_score_count"}:
            sort = "avg_profit_jpy"
        rows.sort(key=lambda r: _num(r, sort), reverse=(order != "asc"))
        items = rows[:limit]
        # summary KPIs
        def _sum(k):
            s = 0.0
            for r in rows:
                try:
                    s += float(r.get(k, 0) or 0)
                except Exception:
                    pass
            return s
        summary = {
            "sellers": len(rows),
            "with_ae": int(_sum("with_ae_candidates")),
            "high": int(_sum("high_score_count")),
            "avg_profit": _sum("avg_profit_jpy") / len(rows) if rows else 0.0,
        }
        return render_template("resale_verified.html", items=items, total=len(rows), path=path, limit=limit, summary=summary)

    @app.route("/resale/verified.json")
    def resale_verified_json():
        path = request.args.get("path", "exports/seller_verified.csv")
        limit = int(request.args.get("limit", 24))
        page = int(request.args.get("page", 1))
        matched_only = request.args.get("matched_only", "0") in ("1", "true", "True")
        min_high = int(request.args.get("min_high", 0) or 0)
        min_avg_profit = float(request.args.get("min_avg_profit", 0) or 0)
        sort = request.args.get("sort", "avg_profit_jpy")
        order = request.args.get("order", "desc")
        rows = _read_csv_rows(path)
        def _keep(r: dict) -> bool:
            try:
                if matched_only and int(r.get("with_ae_candidates", 0) or 0) <= 0:
                    return False
                if min_high and int(r.get("high_score_count", 0) or 0) < min_high:
                    return False
                if min_avg_profit and float(r.get("avg_profit_jpy", 0) or 0) < min_avg_profit:
                    return False
                return True
            except Exception:
                return False
        rows = [r for r in rows if _keep(r)]
        def _num(r, k):
            try:
                return float(r.get(k, 0) or 0)
            except Exception:
                return 0.0
        if sort not in {"avg_profit_jpy","max_score","avg_score","with_ae_candidates","high_score_count"}:
            sort = "avg_profit_jpy"
        rows.sort(key=lambda r: _num(r, sort), reverse=(order != "asc"))
        total = len(rows)
        start = max(0, (page-1)*limit)
        items = rows[start:start+limit]
        return jsonify({"items": items, "total": total, "page": page, "limit": limit})

    # Resale: verified item details (with profit)
    @app.route("/resale/items")
    def resale_items():
        path = request.args.get("path", os.path.join(exports_base, "seller_verified_items.csv"))
        limit = int(request.args.get("limit", 100))
        min_profit = float(request.args.get("min_profit", 0) or 0)
        min_score = float(request.args.get("min_score", 0) or 0)
        matched_only = request.args.get("matched_only", "0") in ("1", "true", "True")
        sort = request.args.get("sort", "est_profit_jpy")
        order = request.args.get("order", "desc")
        rows = _read_csv_rows(path)
        # filter and sort by estimated profit desc
        def _profit(row):
            try:
                return float(row.get("est_profit_jpy", 0) or 0)
            except Exception:
                return 0.0
        def _score(row):
            try:
                return float(row.get("score", 0) or 0)
            except Exception:
                return 0.0
        def _keep(r: dict) -> bool:
            try:
                if matched_only and not (r.get("ae_url") and str(r.get("ae_url")).strip()):
                    return False
                if min_score and _score(r) < min_score:
                    return False
                if _profit(r) < min_profit:
                    return False
                return True
            except Exception:
                return False
        rows = [r for r in rows if _keep(r)]
        def _num(r, k):
            try:
                return float(r.get(k, 0) or 0)
            except Exception:
                return 0.0
        if sort not in {"est_profit_jpy","score","title_sim","price_ratio","yahoo_price"}:
            sort = "est_profit_jpy"
        rows.sort(key=lambda r: _num(r, sort), reverse=(order != "asc"))
        items = rows[:limit]
        return render_template("resale_items.html", items=items, total=len(rows), path=path, limit=limit, min_profit=min_profit)

    @app.route("/resale/items.json")
    def resale_items_json():
        path = request.args.get("path", "exports/seller_verified_items.csv")
        limit = int(request.args.get("limit", 24))
        page = int(request.args.get("page", 1))
        min_profit = float(request.args.get("min_profit", 0) or 0)
        min_score = float(request.args.get("min_score", 0) or 0)
        matched_only = request.args.get("matched_only", "0") in ("1", "true", "True")
        sort = request.args.get("sort", "est_profit_jpy")
        order = request.args.get("order", "desc")
        rows = _read_csv_rows(path)
        def _profit(row):
            try:
                return float(row.get("est_profit_jpy", 0) or 0)
            except Exception:
                return 0.0
        def _score(row):
            try:
                return float(row.get("score", 0) or 0)
            except Exception:
                return 0.0
        def _keep(r: dict) -> bool:
            try:
                if matched_only and not (r.get("ae_url") and str(r.get("ae_url")).strip()):
                    return False
                if min_score and _score(r) < min_score:
                    return False
                if _profit(r) < min_profit:
                    return False
                return True
            except Exception:
                return False
        rows = [r for r in rows if _keep(r)]
        def _num(r, k):
            try:
                return float(r.get(k, 0) or 0)
            except Exception:
                return 0.0
        if sort not in {"est_profit_jpy","score","title_sim","price_ratio","yahoo_price"}:
            sort = "est_profit_jpy"
        rows.sort(key=lambda r: _num(r, sort), reverse=(order != "asc"))
        total = len(rows)
        start = max(0, (page-1)*limit)
        items = rows[start:start+limit]
        return jsonify({"items": items, "total": total, "page": page, "limit": limit})

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="127.0.0.1", port=3500, debug=False)

