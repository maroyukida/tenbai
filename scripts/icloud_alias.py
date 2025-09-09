from __future__ import annotations

"""
Create a new iCloud+ Hide My Email alias via iCloud Web with Playwright.

Notes
- First run requires manual Apple ID login + 2FA in the opened browser window.
- Cookies/session persist in the specified profile directory for reuse.
- Works best in headed mode; headless is supported after login.

Usage
  pip install playwright
  playwright install chromium

  python scripts/icloud_alias.py --label koetomo --note batch1 \
    --profile .playwright-icloud --headless false

It prints the alias as:
  ALIAS_EMAIL: xxxxx@icloud.com
"""

import argparse
import re
from pathlib import Path
from typing import Optional

from playwright.sync_api import TimeoutError as PWTimeoutError
from playwright.sync_api import sync_playwright


HME_URLS = [
    "https://www.icloud.com/icloudplus/hide-my-email",
    "https://www.icloud.com/icloudplus/hidemyemail",
    "https://www.icloud.com/settings/hide-my-email",
    "https://www.icloud.com/",
]


def first_or_none(it):
    for x in it:
        return x
    return None


def find_alias_text(page) -> Optional[str]:
    # Try to extract the first icloud.com address visible on the page
    # 1) Scan common containers
    candidates = [
        "text=/@icloud\.com/",
        "//*/text()[contains(., '@icloud.com')]/..",
    ]
    for sel in candidates:
        try:
            el = page.locator(sel).first
            if el and el.is_visible():
                txt = el.inner_text(timeout=500)
                m = re.search(r"[A-Za-z0-9._%+-]+@icloud\.com", txt)
                if m:
                    return m.group(0)
        except Exception:
            pass
    # 2) Fallback: page content regex
    try:
        content = page.content()
        m = re.search(r"[A-Za-z0-9._%+-]+@icloud\.com", content)
        if m:
            return m.group(0)
    except Exception:
        pass
    return None


def ensure_on_hide_my_email(page) -> None:
    # Try the dedicated URL first; if not rendered yet, user must login
    for url in HME_URLS:
        try:
            page.goto(url, wait_until="load")
            # Wait for a sign of HME screen (Japanese/English)
            page.wait_for_timeout(800)
            page.wait_for_selector("text=/メールを非公開|Hide My Email|メールアドレスを作成|Create new address/", timeout=5000)
            return
        except PWTimeoutError:
            continue
    # If still not present, just stay on current page; user can navigate manually
    return


def click_create_address(page) -> None:
    # i18n button text heuristics
    buttons = [
        page.get_by_role("button", name=re.compile("メールアドレスを作成|新しいメールアドレス|Create new address|Create Email Address", re.I)),
        page.get_by_text(re.compile("メールアドレスを作成|Create.*address", re.I)).locator("xpath=ancestor::button[1]"),
    ]
    for btn in buttons:
        try:
            if btn and btn.is_visible():
                btn.click(timeout=3000)
                page.wait_for_timeout(600)
                return
        except Exception:
            continue


def fill_label_and_note(page, label: Optional[str], note: Optional[str]) -> None:
    # Try placeholders/labels in JP/EN
    selectors = [
        page.get_by_placeholder("アドレスにラベルを追加"),
        page.get_by_placeholder("ラベル"),
        page.get_by_placeholder("Add a label"),
        page.get_by_label(re.compile("ラベル|Label", re.I)),
    ]
    if label:
        for sel in selectors:
            try:
                if sel and sel.is_visible():
                    sel.fill(label)
                    break
            except Exception:
                continue
    if note:
        note_sel = None
        for s in [
            page.get_by_placeholder("メモを作成"),
            page.get_by_placeholder("メモ"),
            page.get_by_placeholder("Note"),
            page.get_by_label(re.compile("メモ|Note", re.I)),
        ]:
            try:
                if s and s.is_visible():
                    note_sel = s; break
            except Exception:
                continue
        if note_sel:
            try:
                note_sel.fill(note)
            except Exception:
                pass


def click_confirm(page) -> None:
    confirms = [
        page.get_by_role("button", name=re.compile("メールアドレスを作成|作成|Create", re.I)),
        page.get_by_text(re.compile("作成|Create", re.I)).locator("xpath=ancestor::button[1]"),
    ]
    for c in confirms:
        try:
            if c and c.is_visible():
                c.click(timeout=3000)
                page.wait_for_timeout(600)
                return
        except Exception:
            continue


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", default=None)
    ap.add_argument("--note", default=None)
    ap.add_argument("--profile", default=".playwright-icloud")
    ap.add_argument("--headless", default="false", choices=["true", "false"]) 
    ap.add_argument("--timeout", type=int, default=180)
    args = ap.parse_args()

    data_dir = Path(args.profile)
    data_dir.mkdir(parents=True, exist_ok=True)
    headless = args.headless.lower() == "true"

    with sync_playwright() as pw:
        ctx = pw.chromium.launch_persistent_context(
            user_data_dir=str(data_dir),
            headless=headless,
        )
        page = ctx.new_page()
        try:
            ensure_on_hide_my_email(page)
            # If not yet loaded, ask user to navigate/login manually
            # and wait until the create button appears.
            try:
                page.wait_for_selector("text=/メールアドレスを作成|Create new address/", timeout=args.timeout * 1000)
            except PWTimeoutError:
                # Proceed anyway; user might already be on creation dialog
                pass

            # Start creation flow
            click_create_address(page)
            # Read alias (previews before confirm)
            alias = find_alias_text(page)
            fill_label_and_note(page, args.label, args.note)
            click_confirm(page)
            # Read alias again after confirm if not found
            if not alias:
                alias = find_alias_text(page)
            if alias:
                print("ALIAS_EMAIL:", alias)
            else:
                # Avoid non-ASCII punctuation to be safe on cp932 consoles
                print("ALIAS_EMAIL: (not detected - complete manually, then re-run)")
            return 0
        finally:
            try:
                ctx.close()
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
