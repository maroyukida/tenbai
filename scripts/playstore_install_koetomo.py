"""
Installs Koetomo from Google Play on a MuMu instance via Appium.

Assumptions
- Appium server is running (default: http://localhost:4725/wd/hub)
- The MuMu instance is booted and reachable by adb (udid like 127.0.0.1:16672)
- UiAutomator2 driver is available

Environment vars (or pass via CLI)
- GOOGLE_EMAIL
- GOOGLE_PASSWORD

Usage
  python scripts/playstore_install_koetomo.py --udid 127.0.0.1:16672 \
      --appium http://localhost:4725/wd/hub --package jp.co.meetscom.koetomo

Notes
- Google login UI changes frequently. The locators below are heuristics.
- If 2FA is enabled, manual intervention may be required.
"""

from __future__ import annotations

import os
import sys
import time
import argparse
from typing import Optional

from appium import webdriver
from appium.options.android import UiAutomator2Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException


def _opts(udid: str) -> UiAutomator2Options:
    caps = UiAutomator2Options()
    caps.platform_name = "Android"
    caps.automation_name = "UiAutomator2"
    caps.udid = udid
    caps.auto_grant_permissions = True
    caps.new_command_timeout = 240
    # Start Play Store
    caps.app_package = "com.android.vending"
    caps.app_activity = "com.google.android.finsky.activities.MainActivity"
    # Make IME typing more reliable
    caps.unicode_keyboard = True
    caps.reset_keyboard = True
    return caps


def _wait(drv: webdriver.Remote, by, value, timeout=25):
    return WebDriverWait(drv, timeout).until(EC.presence_of_element_located((by, value)))


def _click_if_present(drv: webdriver.Remote, by, value) -> bool:
    try:
        el = WebDriverWait(drv, 3).until(EC.element_to_be_clickable((by, value)))
        el.click()
        return True
    except Exception:
        return False


def _enter_text(drv: webdriver.Remote, by, value, text: str, clear: bool = True) -> bool:
    try:
        el = _wait(drv, by, value, 15)
        if clear:
            try:
                el.clear()
            except Exception:
                pass
        el.send_keys(text)
        return True
    except Exception:
        return False


def ensure_signed_in_to_play(drv: webdriver.Remote, email: Optional[str], password: Optional[str]) -> None:
    # If a sign-in prompt exists in Play, go through the flow
    # Texts vary by locale; try both Japanese and English.
    signin_labels = [
        "Sign in", "SIGN IN", "ログイン", "サインイン", "既存のアカウントでログイン",
    ]
    for lbl in signin_labels:
        if _click_if_present(drv, By.XPATH, f"//*[@text='{lbl}']"):
            break
    else:
        # No explicit sign-in button visible; assume already signed in
        return

    if not email or not password:
        raise RuntimeError("Play Store requires login but GOOGLE_EMAIL/GOOGLE_PASSWORD are not set.")

    # Google account chooser might appear first
    if _click_if_present(drv, By.XPATH, "//*[contains(@text,'Use another account') or contains(@text,'別のアカウントを使用')]"):
        time.sleep(1)

    # Email field (WebView). Try common selectors.
    email_candidates = [
        (By.XPATH, "//*[@resource-id='identifierId']"),
        (By.XPATH, "//android.widget.EditText[@text='Email or phone']"),
        (By.XPATH, "//android.widget.EditText[contains(@text,'メール') or contains(@content-desc,'メール')]"),
        (By.CLASS_NAME, "android.widget.EditText"),
    ]
    ok = False
    for by, sel in email_candidates:
        ok = _enter_text(drv, by, sel, email)
        if ok:
            break
    if not ok:
        raise RuntimeError("Could not locate Google email field.")

    # Next button
    next_labels = ["Next", "次へ", "次", "NEXT"]
    clicked = False
    for lbl in next_labels:
        if _click_if_present(drv, By.XPATH, f"//*[@text='{lbl}']"):
            clicked = True
            break
    if not clicked:
        # Fallback resource-id common in webview
        _click_if_present(drv, By.ID, "identifierNext")
    time.sleep(2)

    # Password field
    pwd_candidates = [
        (By.XPATH, "//*[@resource-id='password']//*[@class='android.widget.EditText']"),
        (By.XPATH, "//android.widget.EditText[contains(@text,'パスワード') or contains(@content-desc,'パスワード')]"),
        (By.CLASS_NAME, "android.widget.EditText"),
    ]
    ok = False
    for by, sel in pwd_candidates:
        ok = _enter_text(drv, by, sel, password)
        if ok:
            break
    if not ok:
        # Sometimes password field needs a small delay
        time.sleep(2)
        for by, sel in pwd_candidates:
            ok = _enter_text(drv, by, sel, password)
            if ok:
                break
    if not ok:
        raise RuntimeError("Could not locate Google password field.")

    # Next/Accept
    clicked = False
    for lbl in next_labels + ["同意する", "I agree"]:
        if _click_if_present(drv, By.XPATH, f"//*[@text='{lbl}']"):
            clicked = True
            time.sleep(2)
    # There may be multiple consent pages; just proceed best-effort


def open_play_detail(drv: webdriver.Remote, package_id: str) -> None:
    # Try to use the Play search bar as a stable path
    # Focus search
    if not _click_if_present(drv, By.ID, "com.android.vending:id/search_box_text_input"):
        # Some versions require first tapping the search box container
        _click_if_present(drv, By.ID, "com.android.vending:id/search_box_idle_text")
        time.sleep(0.5)
        _click_if_present(drv, By.ID, "com.android.vending:id/search_box_text_input")
    # Type and submit
    query = "koetomo"
    field_ok = _enter_text(drv, By.ID, "com.android.vending:id/search_box_text_input", query)
    if field_ok:
        # Press enter
        try:
            drv.press_keycode(66)  # KEYCODE_ENTER
        except Exception:
            pass
    time.sleep(2)
    # Click result with app name (try Japanese/English)
    for name in ["Koetomo", "コエトモ", "koetomo"]:
        if _click_if_present(drv, By.XPATH, f"//*[@text='{name}']"):
            break
    # If still not on details, try deep link via activity
    try:
        drv.start_activity("com.android.vending", "com.google.android.finsky.activities.MainActivity", intent_action=None, intent_data=f"market://details?id={package_id}")
    except Exception:
        pass


def install_from_details(drv: webdriver.Remote) -> None:
    # Click Install and wait for Open
    install_labels = ["Install", "インストール"]
    for lbl in install_labels:
        if _click_if_present(drv, By.XPATH, f"//*[@text='{lbl}']"):
            break
    # Some versions use an obfuscated resource-id for the button; try common id
    _click_if_present(drv, By.ID, "com.android.vending:id/right_button")

    # Accept permissions if prompted
    for lbl in ["Continue", "続行", "Accept", "同意する"]:
        _click_if_present(drv, By.XPATH, f"//*[@text='{lbl}']")

    # Wait for Open button
    try:
        _wait(drv, By.XPATH, "//*[@text='Open' or @text='開く']", timeout=300)
    except TimeoutException:
        raise RuntimeError("Timed out waiting for installation to complete.")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--udid", required=True)
    ap.add_argument("--appium", default=os.environ.get("APPIUM_URL", "http://localhost:4725/wd/hub"))
    ap.add_argument("--package", default="jp.co.meetscom.koetomo")
    ap.add_argument("--email", default=os.environ.get("GOOGLE_EMAIL"))
    ap.add_argument("--password", default=os.environ.get("GOOGLE_PASSWORD"))
    args = ap.parse_args()

    opts = _opts(args.udid)
    drv = webdriver.Remote(args.appium, options=opts)
    try:
        ensure_signed_in_to_play(drv, args.email, args.password)
        open_play_detail(drv, args.package)
        install_from_details(drv)
        return 0
    finally:
        try:
            drv.quit()
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main())

