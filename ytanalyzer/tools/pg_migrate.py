# -*- coding: utf-8 -*-
"""
PostgreSQL migration utilities

Usage examples:

  # 1) Create tables in Postgres (reads DSN from POSTGRES_DSN or --dsn)
  python -m ytanalyzer.tools.pg_migrate create-schema --dsn postgresql://user:pass@localhost:5432/ytanalyzer

  # 2) Copy data from current SQLite (data/rss_watch.sqlite) to Postgres
  python -m ytanalyzer.tools.pg_migrate copy --dsn postgresql://user:pass@localhost:5432/ytanalyzer --tables all

  # 3) Incremental sync (idempotent upsert)
  python -m ytanalyzer.tools.pg_migrate sync --dsn postgresql://user:pass@localhost:5432/ytanalyzer

Notes:
 - This tool does NOT switch the app to Postgres; it only migrates data.
 - After verification, we can adapt readers/writers to use Postgres.
"""
from __future__ import annotations

import argparse
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Optional

import psycopg


SQLITE_DB = os.path.join("data", "rss_watch.sqlite")


def iso_parse(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return None


@dataclass
class Pg:
    dsn: str

    def connect(self) -> psycopg.Connection:
        return psycopg.connect(self.dsn)


def create_schema(pg: Pg) -> None:
    ddl = [
        # rss_videos
        """
        create table if not exists rss_videos(
          video_id text primary key,
          channel_id text,
          title text,
          published_at timestamptz,
          length_seconds integer,
          is_shorts integer,
          canonical_url text,
          thumb_hq text,
          thumb_maxres text,
          category text,
          keywords_json text,
          description_snip text,
          is_unlisted integer,
          is_age_restricted integer,
          is_live integer,
          live_start timestamptz,
          live_end timestamptz,
          captions_json text,
          chapters_json text,
          subtitle_text text
        )
        """,
        # rss_videos_discovered
        """
        create table if not exists rss_videos_discovered(
          video_id text primary key,
          channel_id text,
          title text,
          published_at timestamptz,
          discovered_at timestamptz
        )
        """,
        # rss_channels
        """
        create table if not exists rss_channels(
          channel_id text primary key,
          etag text,
          last_modified text,
          last_checked_at timestamptz,
          last_success_at timestamptz,
          last_http_status integer,
          failures integer default 0,
          next_poll_at timestamptz,
          poll_interval_sec integer,
          last_seen_published text,
          last_seen_video_id text,
          inflight integer default 0,
          disabled integer default 0
        )
        """,
        # api_imported_files
        """
        create table if not exists api_imported_files(
          file_name text primary key,
          mtime_utc timestamptz,
          imported_at timestamptz
        )
        """,
        # ytapi_snapshots
        """
        create table if not exists ytapi_snapshots(
          id bigserial primary key,
          video_id text,
          channel_id text,
          channel_title text,
          polled_at timestamptz,
          view_count integer,
          like_count integer,
          comment_count integer,
          duration_seconds integer,
          category_id text,
          live_broadcast_content text
        )
        """,
        "create index if not exists idx_snap_vid_time on ytapi_snapshots(video_id, polled_at)",
        "create index if not exists idx_snap_polled on ytapi_snapshots(polled_at)",
        # trending tables
        """
        create table if not exists trending_ranks(
          video_id text primary key,
          channel_id text,
          channel_title text,
          title text,
          thumb_hq text,
          published_at timestamptz,
          category_id text,
          category_name text,
          is_short integer,
          score double precision,
          d1h double precision,
          d3h double precision,
          d6h double precision,
          likes_per_hour double precision,
          v0 integer,
          v1 integer,
          v3 integer,
          v6 integer,
          current_views integer,
          updated_at timestamptz
        )
        """,
        "create index if not exists idx_trending_score on trending_ranks(score desc)",
        "create index if not exists idx_trending_is_cat on trending_ranks(is_short, category_name)",
        # growth metrics
        """
        create table if not exists growth_metrics(
          video_id text primary key,
          is_short integer,
          category_name text,
          d1h double precision,
          d3h double precision,
          d6h double precision,
          likes_per_hour double precision,
          score double precision,
          current_views integer,
          updated_at timestamptz
        )
        """,
    ]
    with pg.connect() as con:
        with con.cursor() as cur:
            for q in ddl:
                cur.execute(q)
        con.commit()
    print("created/ensured tables + indexes")


def _open_sqlite() -> sqlite3.Connection:
    con = sqlite3.connect(SQLITE_DB)
    con.row_factory = sqlite3.Row
    return con


def _iter_rows(con: sqlite3.Connection, sql: str, batch: int = 5000) -> Iterable[list[sqlite3.Row]]:
    cur = con.cursor()
    cur.execute(sql)
    while True:
        rows = cur.fetchmany(batch)
        if not rows:
            break
        yield rows


def copy_basic(pg: Pg) -> None:
    """Copy rss_videos / rss_videos_discovered / rss_channels / api_imported_files"""
    scon = _open_sqlite()
    with pg.connect() as con:
        curp = con.cursor()
        # rss_videos
        for chunk in _iter_rows(scon, "select * from rss_videos"):
            curp.executemany(
                """
                insert into rss_videos(video_id, channel_id, title, published_at, length_seconds, is_shorts, canonical_url,
                                       thumb_hq, thumb_maxres, category, keywords_json, description_snip, is_unlisted,
                                       is_age_restricted, is_live, live_start, live_end, captions_json, chapters_json, subtitle_text)
                values(%(video_id)s, %(channel_id)s, %(title)s, %(published_at_ts)s, %(length_seconds)s, %(is_shorts)s, %(canonical_url)s,
                       %(thumb_hq)s, %(thumb_maxres)s, %(category)s, %(keywords_json)s, %(description_snip)s, %(is_unlisted)s,
                       %(is_age_restricted)s, %(is_live)s, %(live_start_ts)s, %(live_end_ts)s, %(captions_json)s, %(chapters_json)s, %(subtitle_text)s)
                on conflict(video_id) do nothing
                """,
                [
                    {
                        **dict(r),
                        "published_at_ts": iso_parse(r["published_at"]),
                        "live_start_ts": iso_parse(r.get("live_start")),
                        "live_end_ts": iso_parse(r.get("live_end")),
                    }
                    for r in chunk
                ],
            )
        # rss_videos_discovered
        for chunk in _iter_rows(scon, "select * from rss_videos_discovered"):
            curp.executemany(
                """
                insert into rss_videos_discovered(video_id, channel_id, title, published_at, discovered_at)
                values(%(video_id)s, %(channel_id)s, %(title)s, %(published_at_ts)s, %(discovered_at_ts)s)
                on conflict(video_id) do nothing
                """,
                [
                    {
                        **dict(r),
                        "published_at_ts": iso_parse(r["published_at"]),
                        "discovered_at_ts": iso_parse(r["discovered_at"]),
                    }
                    for r in chunk
                ],
            )
        # rss_channels
        for chunk in _iter_rows(scon, "select * from rss_channels"):
            curp.executemany(
                """
                insert into rss_channels(channel_id, etag, last_modified, last_checked_at, last_success_at, last_http_status,
                                         failures, next_poll_at, poll_interval_sec, last_seen_published, last_seen_video_id,
                                         inflight, disabled)
                values(%(channel_id)s, %(etag)s, %(last_modified)s, %(last_checked_at_ts)s, %(last_success_at_ts)s, %(last_http_status)s,
                       %(failures)s, %(next_poll_at_ts)s, %(poll_interval_sec)s, %(last_seen_published)s, %(last_seen_video_id)s,
                       %(inflight)s, %(disabled)s)
                on conflict(channel_id) do update set
                    etag=excluded.etag,
                    last_modified=excluded.last_modified,
                    last_checked_at=excluded.last_checked_at,
                    last_success_at=excluded.last_success_at,
                    last_http_status=excluded.last_http_status,
                    failures=excluded.failures,
                    next_poll_at=excluded.next_poll_at,
                    poll_interval_sec=excluded.poll_interval_sec,
                    last_seen_published=excluded.last_seen_published,
                    last_seen_video_id=excluded.last_seen_video_id,
                    inflight=excluded.inflight,
                    disabled=excluded.disabled
                """,
                [
                    {
                        **dict(r),
                        "last_checked_at_ts": iso_parse(r.get("last_checked_at")),
                        "last_success_at_ts": iso_parse(r.get("last_success_at")),
                        "next_poll_at_ts": iso_parse(r.get("next_poll_at")),
                    }
                    for r in chunk
                ],
            )
        # api_imported_files
        for chunk in _iter_rows(scon, "select * from api_imported_files"):
            curp.executemany(
                """
                insert into api_imported_files(file_name, mtime_utc, imported_at)
                values(%(file_name)s, %(mtime_ts)s, %(imported_ts)s)
                on conflict(file_name) do update set mtime_utc=excluded.mtime_utc, imported_at=excluded.imported_at
                """,
                [
                    {
                        **dict(r),
                        "mtime_ts": iso_parse(r.get("mtime_utc")),
                        "imported_ts": iso_parse(r.get("imported_at")),
                    }
                    for r in chunk
                ],
            )
        con.commit()
    print("copied: rss_videos, rss_videos_discovered, rss_channels, api_imported_files")


def copy_snapshots_and_trending(pg: Pg, max_rows: int | None = None) -> None:
    scon = _open_sqlite()
    with pg.connect() as con:
        curp = con.cursor()
        # ytapi_snapshots
        copied = 0
        for chunk in _iter_rows(scon, "select * from ytapi_snapshots"):
            curp.executemany(
                """
                insert into ytapi_snapshots(video_id, channel_id, channel_title, polled_at, view_count, like_count,
                                            comment_count, duration_seconds, category_id, live_broadcast_content)
                values(%(video_id)s, %(channel_id)s, %(channel_title)s, %(polled_at_ts)s, %(view_count)s, %(like_count)s,
                       %(comment_count)s, %(duration_seconds)s, %(category_id)s, %(live_broadcast_content)s)
                on conflict do nothing
                """,
                [
                    {
                        **dict(r),
                        "polled_at_ts": iso_parse(r.get("polled_at")),
                    }
                    for r in chunk
                ],
            )
            copied += len(chunk)
            if max_rows and copied >= max_rows:
                break
        # trending_ranks
        for chunk in _iter_rows(scon, "select * from trending_ranks"):
            curp.executemany(
                """
                insert into trending_ranks(video_id, channel_id, channel_title, title, thumb_hq, published_at,
                                           category_id, category_name, is_short, score, d1h, d3h, d6h, likes_per_hour,
                                           v0, v1, v3, v6, current_views, updated_at)
                values(%(video_id)s, %(channel_id)s, %(channel_title)s, %(title)s, %(thumb_hq)s, %(published_at_ts)s,
                       %(category_id)s, %(category_name)s, %(is_short)s, %(score)s, %(d1h)s, %(d3h)s, %(d6h)s, %(likes_per_hour)s,
                       %(v0)s, %(v1)s, %(v3)s, %(v6)s, %(current_views)s, %(updated_at_ts)s)
                on conflict(video_id) do update set
                  channel_id=excluded.channel_id,
                  channel_title=excluded.channel_title,
                  title=excluded.title,
                  thumb_hq=excluded.thumb_hq,
                  published_at=excluded.published_at,
                  category_id=excluded.category_id,
                  category_name=excluded.category_name,
                  is_short=excluded.is_short,
                  score=excluded.score,
                  d1h=excluded.d1h,
                  d3h=excluded.d3h,
                  d6h=excluded.d6h,
                  likes_per_hour=excluded.likes_per_hour,
                  v0=excluded.v0,
                  v1=excluded.v1,
                  v3=excluded.v3,
                  v6=excluded.v6,
                  current_views=excluded.current_views,
                  updated_at=excluded.updated_at
                """,
                [
                    {
                        **dict(r),
                        "published_at_ts": iso_parse(r.get("published_at")),
                        "updated_at_ts": iso_parse(r.get("updated_at")),
                    }
                    for r in chunk
                ],
            )
        # growth_metrics
        for chunk in _iter_rows(scon, "select * from growth_metrics"):
            curp.executemany(
                """
                insert into growth_metrics(video_id, is_short, category_name, d1h, d3h, d6h, likes_per_hour, score, current_views, updated_at)
                values(%(video_id)s, %(is_short)s, %(category_name)s, %(d1h)s, %(d3h)s, %(d6h)s, %(likes_per_hour)s, %(score)s, %(current_views)s, %(updated_at_ts)s)
                on conflict(video_id) do update set
                  is_short=excluded.is_short,
                  category_name=excluded.category_name,
                  d1h=excluded.d1h,
                  d3h=excluded.d3h,
                  d6h=excluded.d6h,
                  likes_per_hour=excluded.likes_per_hour,
                  score=excluded.score,
                  current_views=excluded.current_views,
                  updated_at=excluded.updated_at
                """,
                [
                    {
                        **dict(r),
                        "updated_at_ts": iso_parse(r.get("updated_at")),
                    }
                    for r in chunk
                ],
            )
        con.commit()
    print("copied: ytapi_snapshots (+ trending_ranks, growth_metrics)")


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Migrate data from SQLite to Postgres")
    ap.add_argument("cmd", choices=["create-schema", "copy", "sync"], help="what to do")
    ap.add_argument("--dsn", default=os.getenv("POSTGRES_DSN"), help="Postgres DSN (env POSTGRES_DSN)")
    ap.add_argument("--max-snapshots", type=int, default=0, help="limit snapshots copied (0=all)")
    args = ap.parse_args(argv)
    if not args.dsn:
        print("ERROR: set --dsn or env POSTGRES_DSN e.g. postgresql://user:pass@localhost:5432/ytanalyzer")
        return 2
    pg = Pg(args.dsn)
    if args.cmd == "create-schema":
        create_schema(pg)
        return 0
    if args.cmd == "copy":
        create_schema(pg)
        copy_basic(pg)
        copy_snapshots_and_trending(pg, max_rows=(args.max_snapshots or None))
        return 0
    if args.cmd == "sync":
        # simple sync = ensure schema + copy new basics + copy new snapshots/trending
        create_schema(pg)
        copy_basic(pg)
        copy_snapshots_and_trending(pg, max_rows=(args.max_snapshots or None))
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

