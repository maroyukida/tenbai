# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import threading
import time
from datetime import datetime
from typing import Optional

# Load .env so child processes inherit API keys etc.
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    pass


PY = sys.executable or "python"


def creationflags() -> int:
    if os.name == "nt":
        # hide console windows
        return getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return 0


def now_ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class FileLock:
    def __init__(self, path: str, max_age_sec: int = 30 * 60):
        self.path = path
        self.max_age = max_age_sec

    def acquire(self) -> bool:
        try:
            # remove stale
            if os.path.exists(self.path):
                try:
                    if time.time() - os.path.getmtime(self.path) > self.max_age:
                        os.remove(self.path)
                except Exception:
                    pass
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
                f.write(f"pid={os.getpid()} ts={now_ts()}\n")
            return True
        except FileExistsError:
            return False

    def release(self) -> None:
        try:
            if os.path.exists(self.path):
                os.remove(self.path)
        except Exception:
            pass


def ensure_dir(p: str) -> None:
    os.makedirs(p, exist_ok=True)


def write_log(path: str, text: str) -> None:
    ensure_dir(os.path.dirname(path) or ".")
    try:
        # rotate at ~10MB
        if os.path.exists(path) and os.path.getsize(path) > 10 * 1024 * 1024:
            bak = path + ".1"
            try:
                if os.path.exists(bak):
                    os.remove(bak)
                os.replace(path, bak)
            except Exception:
                pass
        with open(path, "a", encoding="utf-8", newline="") as f:
            f.write(text)
    except Exception:
        pass


def run_once(args: list[str], log_name: str, env: Optional[dict] = None) -> int:
    cp = subprocess.run(args, text=True, capture_output=True, env=env, creationflags=creationflags())
    out = cp.stdout or ""
    err = cp.stderr or ""
    if out:
        write_log(os.path.join("logs", f"{log_name}.log"), f"[{now_ts()}] {out}\n")
    if err:
        write_log(os.path.join("logs", f"{log_name}.log"), f"[{now_ts()}] [ERR] {err}\n")
    return cp.returncode


class HeadlessScheduler:
    def __init__(
        self,
        db: str,
        out_dir: str,
        channels_file: str,
        api_key: Optional[str],
        fetch_iv: int,
        refetch_iv: int,
        rank_iv: int,
        categorize_iv: int,
        serve: bool,
        refetch_window_hours: int,
        refetch_tol: int,
        refetch_qps: float,
        refetch_max_ids: Optional[int] = None,
    ):
        self.db = db
        self.out_dir = out_dir
        self.channels_file = channels_file
        self.api_key = api_key or os.getenv("YOUTUBE_API_KEY")
        self.fetch_iv = max(1, fetch_iv)
        self.refetch_iv = max(1, refetch_iv)
        self.rank_iv = max(1, rank_iv)
        self.categorize_iv = max(1, categorize_iv)
        self.serve = serve
        self.refetch_window_hours = max(1, refetch_window_hours)
        self.refetch_tol = max(1, refetch_tol)
        self.refetch_qps = max(0.1, refetch_qps)
        self.refetch_max_ids = refetch_max_ids if (refetch_max_ids or 0) > 0 else None
        self.stop_evt = threading.Event()
        self.procs: dict[str, subprocess.Popen] = {}

    def _spawn(self, name: str, args: list[str], env: Optional[dict] = None) -> None:
        if name in self.procs and self.procs[name] and self.procs[name].poll() is None:
            return
        env2 = os.environ.copy()
        if env:
            env2.update(env)
        write_log(os.path.join("logs", "scheduler.log"), f"[{now_ts()}] spawn {name}: {' '.join(args)}\n")
        p = subprocess.Popen(args, env=env2, creationflags=creationflags(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        self.procs[name] = p
        t = threading.Thread(target=self._pump_logs, args=(name, p), daemon=True)
        t.start()

    def _pump_logs(self, name: str, proc: subprocess.Popen) -> None:
        try:
            if proc.stdout:
                for line in proc.stdout:
                    if not line:
                        break
                    write_log(os.path.join("logs", f"{name}.log"), f"[{now_ts()}] {line}")
        except Exception:
            pass

    def _kill(self, name: str) -> None:
        p = self.procs.get(name)
        if p and p.poll() is None:
            try:
                p.terminate()
                for _ in range(50):
                    if p.poll() is not None:
                        break
                    time.sleep(0.1)
                if p.poll() is None:
                    p.kill()
            except Exception:
                pass
        self.procs[name] = None

    def start_persistent(self) -> None:
        # RSS watcher
        self._spawn(
            "rss_watch",
            [PY, "-m", "ytanalyzer.cli", "rss-watch", "--channels-file", self.channels_file, "--db", self.db, "--rps", "15", "--concurrency", "200", "--batch", "800", "--tick", "5"],
        )
        # NDJSON exporter (loop)
        self._spawn(
            "rss_export",
            [PY, "-m", "ytanalyzer.cli", "rss-export", "--db", self.db, "--out-dir", self.out_dir, "--window-minutes", "10", "--loop"],
        )
        # Waitress server (optional)
        if self.serve:
            self._spawn("serve", [PY, "scripts/serve_prod.py"])  # 127.0.0.1:5000

    def loop_periodic(self) -> None:
        next_fetch = time.time()
        next_refetch = time.time()
        next_rank = time.time()
        next_categorize = time.time()

        while not self.stop_evt.is_set():
            now = time.time()
            if now >= next_fetch:
                env = {}
                if self.api_key:
                    env["YOUTUBE_API_KEY"] = self.api_key
                args = [PY, "-m", "ytanalyzer.cli", "api-fetch", "--db", self.db, "--in-dir", self.out_dir, "--qps", "1.0"]
                if env.get("YOUTUBE_API_KEY"):
                    args += ["--api-key", env["YOUTUBE_API_KEY"]]
                lock = FileLock(os.path.join("logs", ".lock_api_fetch"), 15 * 60)
                if lock.acquire():
                    try:
                        run_once(args, "api_fetch", env={**os.environ, **env})
                    finally:
                        lock.release()
                next_fetch = now + self.fetch_iv * 60

            if now >= next_refetch:
                env = {}
                if self.api_key:
                    env["YOUTUBE_API_KEY"] = self.api_key
                args = [
                    PY, "-m", "ytanalyzer.cli", "api-refetch",
                    "--db", self.db,
                    "--qps", str(self.refetch_qps),
                    "--tol-minutes", str(self.refetch_tol),
                    "--window-hours", str(self.refetch_window_hours),
                ]
                if self.refetch_max_ids:
                    args += ["--max-ids", str(self.refetch_max_ids)]
                if env.get("YOUTUBE_API_KEY"):
                    args += ["--api-key", env["YOUTUBE_API_KEY"]]
                lock = FileLock(os.path.join("logs", ".lock_api_refetch"), 15 * 60)
                if lock.acquire():
                    try:
                        run_once(args, "api_refetch", env={**os.environ, **env})
                    finally:
                        lock.release()
                next_refetch = now + self.refetch_iv * 60

            if now >= next_rank:
                args = [PY, "-m", "ytanalyzer.cli", "growth-rank", "--db", self.db, "--window-hours", "48", "--tol-minutes", "20"]
                lock = FileLock(os.path.join("logs", ".lock_growth_rank"), 15 * 60)
                if lock.acquire():
                    try:
                        run_once(args, "growth_rank")
                    finally:
                        lock.release()
                next_rank = now + self.rank_iv * 60

            # dictionary auto-promote (daily)
            # runs independently of categorize; safe and fast
            if 'next_promote' not in locals():
                next_promote = now + 24 * 60 * 60
            if now >= next_promote:
                args = [PY, "-m", "ytanalyzer.tools.dict_autopromote", "--db", self.db, "--rules", "config/categories.yml"]
                lock = FileLock(os.path.join("logs", ".lock_dict_autopromote"), 30 * 60)
                if lock.acquire():
                    try:
                        run_once(args, "dict_autopromote")
                    finally:
                        lock.release()
                next_promote = now + 24 * 60 * 60

            # categorize videos (rule+prior)
            if now >= next_categorize:
                args = [PY, "-m", "ytanalyzer.tools.categorizer", "--db", self.db, "--rules", "config/categories.yml", "--since-hours", "6", "--limit", "5000"]
                lock = FileLock(os.path.join("logs", ".lock_categorizer"), 10 * 60)
                if lock.acquire():
                    try:
                        run_once(args, "categorizer")
                    finally:
                        lock.release()
                next_categorize = now + self.categorize_iv * 60

            time.sleep(1)

    def stop(self) -> None:
        self.stop_evt.set()
        for n in ["rss_watch", "rss_export", "serve"]:
            self._kill(n)


def build_arg_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Headless scheduler for YTAnalyzer (service-friendly)")
    ap.add_argument("--db", default="data/rss_watch.sqlite")
    ap.add_argument("--out-dir", default="exports")
    ap.add_argument("--channels-file", default="C:/Users/mouda/Documents/yutura/yutura_channels.ndjson")
    ap.add_argument("--api-key", default=os.getenv("YOUTUBE_API_KEY"))
    ap.add_argument("--fetch-iv", type=int, default=10, help="api-fetch interval minutes")
    ap.add_argument("--refetch-iv", type=int, default=5, help="api-refetch interval minutes")
    ap.add_argument("--rank-iv", type=int, default=5, help="growth-rank interval minutes")
    ap.add_argument("--categorize-iv", type=int, default=10, help="categorizer interval minutes")
    ap.add_argument("--serve", action="store_true", help="also start Waitress web server")
    ap.add_argument("--refetch-window-hours", type=int, default=30, help="api-refetch discovery window hours (e.g. 8 for only 1/3/6h)")
    ap.add_argument("--refetch-tol", type=int, default=15, help="api-refetch tolerance minutes around targets")
    ap.add_argument("--refetch-qps", type=float, default=1.5, help="api-refetch QPS upper bound")
    ap.add_argument("--refetch-max-ids", type=int, default=0, help="api-refetch max videos per run (0=unlimited)")
    # auto-discover (optional). set --discover-iv 0 to disable
    ap.add_argument("--discover-iv", type=int, default=30, help="auto-discover interval minutes (0=disable)")
    ap.add_argument("--discover-batch", type=int, default=200, help="auto-discover batch size per run")
    ap.add_argument("--discover-sleep-min", type=float, default=0.8)
    ap.add_argument("--discover-sleep-max", type=float, default=2.0)
    ap.add_argument("--discover-state", type=str, default="data/yutura_auto_discover.json")
    return ap


def main(argv: Optional[list[str]] = None) -> int:
    ap = build_arg_parser()
    args = ap.parse_args(argv)
    sched = HeadlessScheduler(
        db=args.db,
        out_dir=args.out_dir,
        channels_file=args.channels_file,
        api_key=args.api_key,
        fetch_iv=args.fetch_iv,
        refetch_iv=args.refetch_iv,
        rank_iv=args.rank_iv,
        categorize_iv=args.categorize_iv,
        serve=bool(args.serve),
        refetch_window_hours=args.refetch_window_hours,
        refetch_tol=args.refetch_tol,
        refetch_qps=args.refetch_qps,
        refetch_max_ids=(args.refetch_max_ids or None),
    )

    def _sigterm(_signo, _frame):
        write_log(os.path.join("logs", "scheduler.log"), f"[{now_ts()}] received signal, stopping...\n")
        sched.stop()

    try:
        signal.signal(signal.SIGTERM, _sigterm)
    except Exception:
        pass
    try:
        sched.start_persistent()
        # timers for discover
        next_discover = time.time()
        while not sched.stop_evt.is_set():
            now = time.time()
            # periodic jobs inside
            sched.loop_periodic()
            # auto-discover (non-blocking, small batch)
            if args.discover_iv and now >= next_discover:
                # call: python -m ytanalyzer.tools.auto_discover --out <channels-file>
                args_list = [
                    PY, "-m", "ytanalyzer.tools.auto_discover",
                    "--out", args.channels_file,
                    "--state", args.discover_state,
                    "--batch", str(args.discover_batch),
                    "--sleep-min", str(args.discover_sleep_min),
                    "--sleep-max", str(args.discover_sleep_max),
                ]
                # run once; ignore failure
                try:
                    run_once(args_list, "auto_discover")
                except Exception:
                    pass
                next_discover = now + max(1, args.discover_iv) * 60
    except KeyboardInterrupt:
        pass
    finally:
        sched.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
