# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import sys
import threading
import time
import subprocess
import webbrowser
from tkinter import Tk, StringVar, IntVar, ttk, N, S, E, W
from tkinter import scrolledtext
import queue
from datetime import datetime


PY = sys.executable or "python"


class OneClickApp:
    def __init__(self, root: Tk):
        self.root = root
        root.title("YTAnalyzer One-Click Launcher")

        # Config vars
        self.db = StringVar(value=os.getenv("RSS_DB_PATH", "data/rss_watch.sqlite"))
        self.out_dir = StringVar(value=os.getenv("EXPORTS_DIR", "exports"))
        self.api_key = StringVar(value=os.getenv("YOUTUBE_API_KEY", ""))
        self.channels_file = StringVar(value=os.getenv("CHANNELS_NDJSON", "C:/Users/mouda/Documents/yutura/yutura_channels.ndjson"))

        # toggles
        self.t_rss_watch = IntVar(value=1)
        self.t_rss_export = IntVar(value=1)
        self.t_api_fetch = IntVar(value=1)
        self.t_api_refetch = IntVar(value=1)
        self.t_growth_rank = IntVar(value=1)
        self.t_serve = IntVar(value=1)

        # intervals (minutes)
        self.iv_fetch = StringVar(value="10")
        self.iv_refetch = StringVar(value="5")
        self.iv_rank = StringVar(value="5")

        # process handles
        self.procs = {}
        self._loop_threads: list[threading.Thread] = []
        self._stop_event = threading.Event()

        self._build_ui()

    def _build_ui(self):
        frm = ttk.Frame(self.root, padding=12)
        frm.grid(column=0, row=0, sticky=(N, S, E, W))
        for i in range(2):
            frm.columnconfigure(i, weight=1)

        # Paths
        ttk.Label(frm, text="DB (rss_watch.sqlite)").grid(column=0, row=0, sticky=W)
        ttk.Entry(frm, textvariable=self.db, width=60).grid(column=1, row=0, sticky=(E, W))
        ttk.Label(frm, text="Exports Dir").grid(column=0, row=1, sticky=W)
        ttk.Entry(frm, textvariable=self.out_dir, width=60).grid(column=1, row=1, sticky=(E, W))
        ttk.Label(frm, text="Channels NDJSON").grid(column=0, row=2, sticky=W)
        ttk.Entry(frm, textvariable=self.channels_file, width=60).grid(column=1, row=2, sticky=(E, W))
        ttk.Label(frm, text="YouTube API Key").grid(column=0, row=3, sticky=W)
        ttk.Entry(frm, textvariable=self.api_key, width=60, show="*").grid(column=1, row=3, sticky=(E, W))

        # Toggles
        row = 4
        ttk.Checkbutton(frm, text="RSS Watcher (常駐)", variable=self.t_rss_watch).grid(column=0, row=row, sticky=W); row += 1
        ttk.Checkbutton(frm, text="NDJSON Export (10分毎)", variable=self.t_rss_export).grid(column=0, row=row, sticky=W); row += 1
        ttk.Checkbutton(frm, text="API Fetch (10分毎)", variable=self.t_api_fetch).grid(column=0, row=row, sticky=W)
        ttk.Entry(frm, textvariable=self.iv_fetch, width=6).grid(column=1, row=row-0, sticky=W); row += 1
        ttk.Checkbutton(frm, text="API Refetch (5分毎)", variable=self.t_api_refetch).grid(column=0, row=row, sticky=W)
        ttk.Entry(frm, textvariable=self.iv_refetch, width=6).grid(column=1, row=row-0, sticky=W); row += 1
        ttk.Checkbutton(frm, text="Growth Rank (5-10分毎)", variable=self.t_growth_rank).grid(column=0, row=row, sticky=W)
        ttk.Entry(frm, textvariable=self.iv_rank, width=6).grid(column=1, row=row-0, sticky=W); row += 1
        ttk.Checkbutton(frm, text="Web Server (Flask)", variable=self.t_serve).grid(column=0, row=row, sticky=W); row += 1

        # Buttons
        btns = ttk.Frame(frm)
        btns.grid(column=0, row=row, columnspan=2, pady=(10, 0), sticky=(E, W))
        ttk.Button(btns, text="Start All", command=self.start_all).grid(column=0, row=0, padx=4)
        ttk.Button(btns, text="Stop All", command=self.stop_all).grid(column=1, row=0, padx=4)
        ttk.Button(btns, text="Open Trending", command=lambda: webbrowser.open("http://127.0.0.1:5000/trending?view=list")).grid(column=2, row=0, padx=4)
        ttk.Button(btns, text="Exit", command=self.on_exit).grid(column=3, row=0, padx=4)

        # One-off runners
        runners = ttk.Frame(frm)
        runners.grid(column=0, row=row+1, columnspan=2, pady=(8, 0), sticky=(E, W))
        ttk.Label(runners, text="Run once:").grid(column=0, row=0, padx=(0,6))
        ttk.Button(runners, text="API Fetch", command=self._job_api_fetch).grid(column=1, row=0, padx=2)
        ttk.Button(runners, text="API Refetch", command=self._job_api_refetch).grid(column=2, row=0, padx=2)
        ttk.Button(runners, text="Growth Rank", command=self._job_growth_rank).grid(column=3, row=0, padx=2)
        ttk.Button(runners, text="Serve (Prod)", command=self._job_serve_prod).grid(column=4, row=0, padx=8)

        # File logging options
        flf = ttk.Frame(frm)
        flf.grid(column=0, row=row+2, columnspan=2, pady=(6, 0), sticky=(E, W))
        self.enable_filelog = IntVar(value=0)
        self.log_dir = StringVar(value=os.path.join("logs"))
        ttk.Checkbutton(flf, text="Log to files", variable=self.enable_filelog).grid(column=0, row=0, sticky=W)
        ttk.Label(flf, text="Dir:").grid(column=1, row=0, padx=(10,2))
        ttk.Entry(flf, textvariable=self.log_dir, width=40).grid(column=2, row=0, sticky=(E, W))
        ttk.Button(flf, text="Open Dir", command=self._open_log_dir).grid(column=3, row=0, padx=6)

        # Logs panel
        logfrm = ttk.LabelFrame(frm, text="Logs", padding=6)
        logfrm.grid(column=0, row=row+3, columnspan=2, sticky=(N, S, E, W), pady=(12,0))
        frm.rowconfigure(row+3, weight=1)
        logfrm.columnconfigure(0, weight=1)
        logfrm.rowconfigure(1, weight=1)

        self.filter_name = StringVar(value="ALL")
        self.autoscroll = IntVar(value=1)
        controls = ttk.Frame(logfrm)
        controls.grid(column=0, row=0, sticky=(E, W))
        ttk.Label(controls, text="Filter:").grid(column=0, row=0, padx=(0,6))
        self.filter_cb = ttk.Combobox(controls, values=["ALL","rss_watch","rss_export","serve","api_fetch","api_refetch","growth_rank"], textvariable=self.filter_name, width=16)
        self.filter_cb.grid(column=1, row=0)
        ttk.Checkbutton(controls, text="Auto-Scroll", variable=self.autoscroll).grid(column=2, row=0, padx=10)
        ttk.Button(controls, text="Clear", command=self._clear_logs).grid(column=3, row=0)

        self.log_text = scrolledtext.ScrolledText(logfrm, height=18, wrap='word')
        self.log_text.grid(column=0, row=1, sticky=(N,S,E,W))
        self.log_text.configure(state='disabled')

        # log queue + pump
        self._logq = queue.Queue()
        self.root.after(100, self._drain_logs)

    # ==== Process helpers ====
    def _spawn(self, name: str, args: list[str], env: dict | None = None):
        if name in self.procs and self.procs[name] and self.procs[name].poll() is None:
            return
        env2 = os.environ.copy()
        if env:
            env2.update(env)
        self._log(f"{name}", f"[spawn] {' '.join(args)}")
        self.procs[name] = subprocess.Popen(
            args,
            env=env2,
            creationflags=self._creationflags(),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        self._attach_log_reader(name, self.procs[name])

    def _creationflags(self):
        # Avoid opening new console windows on Windows
        if os.name == "nt":
            return subprocess.CREATE_NO_WINDOW
        return 0

    def _kill(self, name: str):
        p = self.procs.get(name)
        if p and p.poll() is None:
            try:
                p.terminate()
                for _ in range(20):
                    if p.poll() is not None:
                        break
                    time.sleep(0.1)
                if p.poll() is None:
                    p.kill()
            except Exception:
                pass
        self.procs[name] = None

    # ==== Start/Stop ====
    def start_all(self):
        self._stop_event.clear()

        if self.t_rss_watch.get():
            self._spawn(
                "rss_watch",
                [PY, "-m", "ytanalyzer.cli", "rss-watch",
                 "--channels-file", self.channels_file.get(),
                 "--db", self.db.get(), "--rps", "15", "--concurrency", "200", "--batch", "800", "--tick", "5"],
            )

        if self.t_rss_export.get():
            self._spawn(
                "rss_export",
                [PY, "-m", "ytanalyzer.cli", "rss-export", "--db", self.db.get(), "--out-dir", self.out_dir.get(), "--window-minutes", "10", "--loop"],
            )

        if self.t_serve.get():
            self._spawn("serve", [PY, "-m", "ytanalyzer.cli", "serve"])  # 127.0.0.1:5000

        # Periodic short-run tasks
        if self.t_api_fetch.get():
            t = threading.Thread(target=self._loop_task,
                                 args=("api_fetch", int(self.iv_fetch.get() or "10"), self._job_api_fetch), daemon=True)
            t.start(); self._loop_threads.append(t)
        if self.t_api_refetch.get():
            t = threading.Thread(target=self._loop_task,
                                 args=("api_refetch", int(self.iv_refetch.get() or "5"), self._job_api_refetch), daemon=True)
            t.start(); self._loop_threads.append(t)
        if self.t_growth_rank.get():
            t = threading.Thread(target=self._loop_task,
                                 args=("growth_rank", int(self.iv_rank.get() or "5"), self._job_growth_rank), daemon=True)
            t.start(); self._loop_threads.append(t)

    def stop_all(self):
        self._stop_event.set()
        # Kill long running processes
        for name in ["rss_watch", "rss_export", "serve"]:
            self._kill(name)

    def on_exit(self):
        self.stop_all()
        self.root.after(200, self.root.destroy)

    # ==== Loop & Jobs ====
    def _loop_task(self, name: str, minutes: int, fn):
        # First run immediately, then every N minutes
        while not self._stop_event.is_set():
            try:
                fn()
            except Exception as e:
                self._log(name, f"error: {e}")
            # wait
            for _ in range(max(1, minutes*60)):
                if self._stop_event.is_set():
                    return
                time.sleep(1)

    def _job_api_fetch(self):
        env = {"YOUTUBE_API_KEY": self.api_key.get() or os.getenv("YOUTUBE_API_KEY", "")}
        args = [PY, "-m", "ytanalyzer.cli", "api-fetch", "--db", self.db.get(), "--in-dir", self.out_dir.get(), "--qps", "1.0"]
        if env.get("YOUTUBE_API_KEY"):
            args += ["--api-key", env["YOUTUBE_API_KEY"]]
        cp = subprocess.run(args, env={**os.environ, **env}, creationflags=self._creationflags(), capture_output=True, text=True)
        if cp.stdout:
            self._log("api_fetch", cp.stdout.strip())
        if cp.stderr:
            self._log("api_fetch", cp.stderr.strip())

    def _job_api_refetch(self):
        env = {"YOUTUBE_API_KEY": self.api_key.get() or os.getenv("YOUTUBE_API_KEY", "")}
        args = [PY, "-m", "ytanalyzer.cli", "api-refetch", "--db", self.db.get(), "--qps", "1.5", "--tol-minutes", "15", "--window-hours", "30"]
        if env.get("YOUTUBE_API_KEY"):
            args += ["--api-key", env["YOUTUBE_API_KEY"]]
        cp = subprocess.run(args, env={**os.environ, **env}, creationflags=self._creationflags(), capture_output=True, text=True)
        if cp.stdout:
            self._log("api_refetch", cp.stdout.strip())
        if cp.stderr:
            self._log("api_refetch", cp.stderr.strip())

    def _job_growth_rank(self):
        args = [PY, "-m", "ytanalyzer.cli", "growth-rank", "--db", self.db.get(), "--window-hours", "48", "--tol-minutes", "20"]
        cp = subprocess.run(args, creationflags=self._creationflags(), capture_output=True, text=True)
        if cp.stdout:
            self._log("growth_rank", cp.stdout.strip())
        if cp.stderr:
            self._log("growth_rank", cp.stderr.strip())

    # ==== Logging helpers ====
    def _attach_log_reader(self, name: str, proc: subprocess.Popen):
        def reader():
            try:
                if proc.stdout:
                    for line in proc.stdout:
                        if not line:
                            break
                        self._log(name, line.rstrip())
            except Exception:
                pass
        t = threading.Thread(target=reader, daemon=True)
        t.start()

    def _log(self, name: str, msg: str):
        ts = datetime.now().strftime('%H:%M:%S')
        for ln in (msg.splitlines() or [""]):
            self._logq.put((name, ts, ln))
            self._write_file_log(name, f"[{ts}] {name}: {ln}\n")

    def _drain_logs(self):
        try:
            while True:
                name, ts, ln = self._logq.get_nowait()
                if self.filter_name.get() not in ("ALL", name):
                    # keep but do not show — for simplicity, we drop filtered lines
                    continue
                self.log_text.configure(state='normal')
                self.log_text.insert('end', f"[{ts}] {name}: {ln}\n")
                if self.autoscroll.get():
                    self.log_text.see('end')
                self.log_text.configure(state='disabled')
        except queue.Empty:
            pass
        finally:
            self.root.after(200, self._drain_logs)

    def _clear_logs(self):
        self.log_text.configure(state='normal')
        self.log_text.delete('1.0', 'end')
        self.log_text.configure(state='disabled')

    # ==== File logging ====
    def _log_path(self, name: str) -> str:
        d = self.log_dir.get().strip() or "logs"
        os.makedirs(d, exist_ok=True)
        return os.path.join(d, f"{name}.log")

    def _rotate_if_needed(self, path: str, max_bytes: int = 10*1024*1024):
        try:
            if os.path.exists(path) and os.path.getsize(path) > max_bytes:
                bak = path + ".1"
                if os.path.exists(bak):
                    try:
                        os.remove(bak)
                    except Exception:
                        pass
                try:
                    os.replace(path, bak)
                except Exception:
                    pass
        except Exception:
            pass

    def _write_file_log(self, name: str, text: str):
        if not self.enable_filelog.get():
            return
        try:
            p = self._log_path(name)
            self._rotate_if_needed(p)
            with open(p, 'a', encoding='utf-8', newline='') as f:
                f.write(text)
        except Exception:
            pass

    def _open_log_dir(self):
        d = self.log_dir.get().strip() or "logs"
        os.makedirs(d, exist_ok=True)
        try:
            if os.name == 'nt':
                os.startfile(d)  # type: ignore[attr-defined]
            elif sys.platform == 'darwin':
                subprocess.run(['open', d])
            else:
                subprocess.run(['xdg-open', d])
        except Exception:
            pass

    # ==== Prod serve (Waitress) ====
    def _job_serve_prod(self):
        # Start Waitress in foreground once; useful for testing
        args = [PY, "scripts/serve_prod.py"]
        cp = subprocess.run(args, creationflags=self._creationflags(), capture_output=True, text=True)
        if cp.stdout:
            self._log("serve", cp.stdout.strip())
        if cp.stderr:
            self._log("serve", cp.stderr.strip())


def main():
    root = Tk()
    app = OneClickApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
