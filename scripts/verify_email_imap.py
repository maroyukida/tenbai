from __future__ import annotations

import argparse
import email
import imaplib
import re
import ssl
import time
import subprocess
from typing import Optional


URL_RE = re.compile(r"https?://[\w\-\._~:/?#\[\]@!$&'()*+,;=%]+", re.I)


def open_url_in_emulator(udid: str, url: str) -> None:
    cmd = [
        r"C:\\Program Files\\Netease\\MuMuPlayerGlobal-12.0\\shell\\adb.exe",
        "-s",
        udid,
        "shell",
        "am",
        "start",
        "-a",
        "android.intent.action.VIEW",
        "-d",
        url,
    ]
    subprocess.check_call(cmd)


def _imap_search_first_ok(imap: imaplib.IMAP4_SSL, queries: list[tuple]) -> list[bytes]:
    for q in queries:
        typ, data = imap.search(None, *q)
        if typ == "OK" and data and data[0]:
            ids = (data[0] or b"").split()
            if ids:
                return ids
    return []


def fetch_latest_matching(
    host: str,
    user: str,
    app_pass: str,
    mailbox: str = "INBOX",
    to_filter: Optional[str] = None,
    subject_hint: Optional[str] = None,
    timeout: int = 600,
    interval: int = 5,
    include_seen: bool = False,
) -> Optional[email.message.Message]:
    ctx = ssl.create_default_context()
    end = time.time() + timeout
    while time.time() < end:
        with imaplib.IMAP4_SSL(host, 993, ssl_context=ctx) as imap:
            imap.login(user, app_pass)
            imap.select(mailbox)
            # Build candidate searches (Gmail/iCloud differences)
            base = [] if include_seen else ["UNSEEN"]
            if subject_hint:
                base += ["SUBJECT", subject_hint]
            searches: list[tuple] = []
            if to_filter:
                # Try To -> Delivered-To -> X-Original-To
                searches.append(tuple(base + ["HEADER", "To", to_filter]))
                searches.append(tuple(base + ["HEADER", "Delivered-To", to_filter]))
                searches.append(tuple(base + ["HEADER", "X-Original-To", to_filter]))
            # Fallback: just base criteria
            searches.append(tuple(base))

            ids = _imap_search_first_ok(imap, searches)
            if not ids:
                time.sleep(interval)
                continue
            last_id = ids[-1]
            typ, msg_data = imap.fetch(last_id, "(RFC822)")
            if typ != "OK":
                time.sleep(interval)
                continue
            raw = msg_data[0][1]
            msg = email.message_from_bytes(raw)
            return msg
        time.sleep(interval)
    return None


def get_body_text(msg: email.message.Message) -> str:
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            if ctype in ("text/html", "text/plain"):
                try:
                    return part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", errors="ignore")
                except Exception:
                    continue
    else:
        try:
            return msg.get_payload(decode=True).decode(msg.get_content_charset() or "utf-8", errors="ignore")
        except Exception:
            pass
    return ""


def first_url(text: str, host_hint: Optional[str] = None) -> Optional[str]:
    for m in URL_RE.finditer(text or ""):
        u = m.group(0)
        if (host_hint is None) or (host_hint.lower() in u.lower()):
            return u
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--udid", required=True)
    ap.add_argument("--host", default="imap.mail.me.com")
    ap.add_argument("--user", required=True, help="iCloud email (login user)")
    ap.add_argument("--app-pass", required=True, help="App-specific password for IMAP")
    ap.add_argument("--to", required=False, help="Alias address (recipient filter)")
    ap.add_argument("--subject", default=None)
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--host-hint", default=None, help="Filter verification link host (optional)")
    ap.add_argument("--mailbox", default="INBOX")
    ap.add_argument("--include-seen", action="store_true", help="Search seen mails too (fallback)")
    args = ap.parse_args()

    msg = fetch_latest_matching(
        host=args.host,
        user=args.user,
        app_pass=args.app_pass,
        mailbox=args.mailbox,
        to_filter=args.to,
        subject_hint=args.subject,
        timeout=args.timeout,
        include_seen=args.include_seen,
    )
    if not msg:
        print("No matching mail found within timeout.")
        return 2
    body = get_body_text(msg)
    url = first_url(body, args.host_hint)
    if not url:
        print("No URL found in message. Body follows:\n", body[:1200])
        return 3
    print("VERIFY_URL:", url)
    open_url_in_emulator(args.udid, url)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
