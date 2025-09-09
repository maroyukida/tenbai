from __future__ import annotations

"""
End-to-end helper:
  - Create a temp mailbox (1secmail or mail.tm)
  - Print address to stdout (use it in Koetomo sign-up)
  - Poll mailbox for the Koetomo verification email
  - Extract first URL and open it in the MuMu emulator via adb

Usage:
  python scripts/verify_koetomo_email.py --udid 127.0.0.1:16672 \
      --provider 1secmail --subject-hint koetomo

Notes:
  - You still need to drive the Koetomo UI (Appium or manually) to request the email.
  - If Koetomo uses a numeric code instead of a link, adapt to parse the code
    and input it via Appium (see comment in code).
"""

import argparse
import subprocess
import sys
from typing import Optional

from temp_email import create_mailbox, poll_message, first_url_from_html


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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--udid", required=True)
    ap.add_argument("--provider", default="1secmail", choices=["1secmail", "mailtm"])
    ap.add_argument("--subject-hint", default="koetomo")
    ap.add_argument("--host-hint", default=None)
    ap.add_argument("--timeout", type=int, default=240)
    args = ap.parse_args()

    box = create_mailbox(args.provider)
    print("TEMP_EMAIL:", box.address, flush=True)
    print("Use this address in Koetomo sign-up.", flush=True)

    msg, html = poll_message(box, timeout=args.timeout, subject_hint=args.subject_hint)
    url = first_url_from_html(html, host_hint=args.host_hint)
    if not url:
        print("Could not find verification URL in email body.")
        # If it's a numeric code flow, you can parse it like:
        #   import re; code = re.search(r"\b(\d{4,8})\b", html or ""); ... use Appium to type it ...
        return 2
    print("VERIFY_URL:", url, flush=True)
    open_url_in_emulator(args.udid, url)
    print("Verification URL opened in emulator.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

