"""
Bootstrap first-run registration flow for Koetomo (best-effort, heuristic).

This is a starter script; adjust selectors to your current app version.
"""

from __future__ import annotations

import os
import sys
import json
import time
import random
import argparse
from typing import Optional, List, Set

from appium import webdriver
from appium.options.android import UiAutomator2Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


def _opts(udid: str) -> UiAutomator2Options:
    caps = UiAutomator2Options()
    caps.platform_name = "Android"
    caps.automation_name = "UiAutomator2"
    caps.udid = udid
    caps.auto_grant_permissions = True
    caps.new_command_timeout = 240
    caps.app_package = "jp.co.meetscom.koetomo"
    # Resolved via: adb shell cmd package resolve-activity -a android.intent.action.MAIN -c android.intent.category.LAUNCHER jp.co.meetscom.koetomo
    caps.app_activity = "jp.co.meetscom.koetomo.controller.top.RootViewActivity"
    caps.unicode_keyboard = True
    caps.reset_keyboard = True
    return caps


def _click_text(drv: webdriver.Remote, *texts: str, timeout: int = 3) -> bool:
    for t in texts:
        try:
            el = WebDriverWait(drv, timeout).until(EC.element_to_be_clickable((By.XPATH, f"//*[@text='{t}']")))
            el.click()
            return True
        except Exception:
            continue
    return False


def _enter_text_by_hint(drv: webdriver.Remote, hints: List[str], text: str) -> bool:
    for h in hints:
        try:
            el = WebDriverWait(drv, 3).until(EC.presence_of_element_located((By.XPATH, f"//android.widget.EditText[@text='{h}' or @content-desc='{h}']")))
            el.send_keys(text)
            return True
        except Exception:
            continue
    return False


def enter_email_if_present(drv: webdriver.Remote, email: str) -> bool:
    # Try common resource-id patterns first
    id_candidates = [
        "jp.co.meetscom.koetomo:id/email",
        "jp.co.meetscom.koetomo:id/mail",
        "jp.co.meetscom.koetomo:id/email_input",
        "jp.co.meetscom.koetomo:id/text_email",
    ]
    for rid in id_candidates:
        try:
            el = WebDriverWait(drv, 2).until(EC.presence_of_element_located((By.ID, rid)))
            el.clear(); el.send_keys(email)
            return True
        except Exception:
            continue
    # Fallback to EditText with hint/placeholder text
    hints = ["メール", "メールアドレス", "Eメール", "Email", "E-mail"]
    if _enter_text_by_hint(drv, hints, email):
        return True
    # As a last resort, try the first EditText on screen
    try:
        el = WebDriverWait(drv, 2).until(EC.presence_of_element_located((By.CLASS_NAME, "android.widget.EditText")))
        el.clear(); el.send_keys(email)
        return True
    except Exception:
        return False


def tap_submit_if_present(drv: webdriver.Remote) -> bool:
    labels = [
        "送信", "登録", "認証", "確認", "次へ", "完了", "開始", "Sign up", "Submit", "Next", "Continue",
        "認証メールを送信", "メールを送信",
    ]
    for lb in labels:
        if _click_text(drv, lb):
            return True
    # Try a generic button by resource-id
    for rid in [
        "jp.co.meetscom.koetomo:id/submit",
        "jp.co.meetscom.koetomo:id/button",
        "jp.co.meetscom.koetomo:id/confirm",
        "jp.co.meetscom.koetomo:id/continue",
    ]:
        try:
            el = WebDriverWait(drv, 1).until(EC.element_to_be_clickable((By.ID, rid)))
            el.click(); return True
        except Exception:
            continue
    return False


def first_run_consent(drv: webdriver.Remote) -> None:
    for _ in range(6):
        acted = False
        acted |= _click_text(drv, "OK", "同意する", "許可", "続行", "次へ", "確認", "同意して進む")
        # Explicit: if the mail sign-up button is present on the top screen, tap it
        try:
            el = WebDriverWait(drv, 1).until(EC.element_to_be_clickable((By.ID, "jp.co.meetscom.koetomo:id/mail_signup_button")))
            el.click(); acted = True
        except Exception:
            pass
        if not acted:
            time.sleep(0.8)


def _gen_base_hiragana() -> str:
    # Generate a soft-sounding base like "ふぉる" or "みお" by concatenating syllables
    syllables = [
        "あ","い","う","え","お",
        "か","き","く","け","こ",
        "さ","し","す","せ","そ",
        "た","ち","つ","て","と",
        "な","に","ぬ","ね","の",
        "は","ひ","ふ","へ","ほ",
        "ま","み","む","め","も",
        "や","ゆ","よ",
        "ら","り","る","れ","ろ",
        "わ","を","ん",
        # small kana for combined sounds
        "ふぁ","ふぃ","ふぇ","ふぉ",
        "しゃ","しゅ","しょ","ちゃ","ちゅ","ちょ",
        "りゅ","りょ","にゃ","にゅ","にょ",
    ]
    n = random.choice([2, 3])
    return "".join(random.choice(syllables) for _ in range(n))


def generate_random_nickname(style: str = "san-dots") -> str:
    base = _gen_base_hiragana()
    if style == "san-dots":
        dots = random.choice(["…", "。。", "。。。"])
        return f"{base}さん{dots}"
    return base


def load_used_names(path: str) -> Set[str]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return set(data)
            return set()
    except Exception:
        return set()


def save_used_names(path: str, used: Set[str], cap: int = 2000) -> None:
    lst = list(used)
    if len(lst) > cap:
        lst = lst[-cap:]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(lst, f, ensure_ascii=False)


def unique_nickname(style: str, store_path: str) -> str:
    used = load_used_names(store_path)
    for _ in range(50):
        name = generate_random_nickname(style=style)
        if name not in used:
            used.add(name)
            save_used_names(store_path, used)
            return name
    # Fallback: force uniqueness with digits
    name = f"{generate_random_nickname(style=style)}{random.randint(10,99)}"
    used.add(name)
    save_used_names(store_path, used)
    return name


def try_registration(
    drv: webdriver.Remote,
    nickname: Optional[str],
    gender: Optional[str] = None,
    age: Optional[int] = None,
) -> None:
    # Tap "新規登録" / "Sign up" if present
    _click_text(drv, "新規登録", "アカウント作成", "Sign up", "Create account")

    if nickname:
        _enter_text_by_hint(drv, ["ニックネーム", "ユーザー名", "Nickname", "Name"], nickname)

    # Gender (heuristic)
    if gender:
        g = gender.lower()
        if g.startswith("m") or g.startswith("男"):
            _click_text(drv, "男性", "Male")
        elif g.startswith("f") or g.startswith("女"):
            _click_text(drv, "女性", "Female")
        else:
            _click_text(drv, "未選択", "その他", "Other")

    # Age selection (heuristic)
    _click_text(drv, "年齢", "Age")
    if age is None:
        _click_text(drv, "18-24", "25-34", "35-44", "45-54", "55+", "18～24", "25～34", "35～44", "45～54", "55+")
    else:
        if 18 <= age <= 24:
            _click_text(drv, "18-24", "18～24")
        elif 25 <= age <= 34:
            _click_text(drv, "25-34", "25～34")
        elif 35 <= age <= 44:
            _click_text(drv, "35-44", "35～44")
        elif 45 <= age <= 54:
            _click_text(drv, "45-54", "45～54")
        else:
            _click_text(drv, "55+", "55 以上", "55以上")

    # Proceed/submit heuristics
    _click_text(drv, "始める", "登録", "完了", "次へ", "Start", "Continue", "Done")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--udid", required=True)
    ap.add_argument("--appium", default=os.environ.get("APPIUM_URL", "http://localhost:4725/wd/hub"))
    ap.add_argument("--nickname", default=None, help="Explicit nickname. Omit to auto-generate.")
    ap.add_argument("--email", default=None, help="Email address to input on sign-up screen (optional)")
    ap.add_argument("--gender", default="male", help="male/female/other")
    ap.add_argument("--age", type=int, default=27)
    ap.add_argument("--name-style", default="san-dots", help="random name style (default: san-dots)")
    ap.add_argument("--unique-store", default=os.path.join(os.path.dirname(__file__), "data", "used_names.json"))
    args = ap.parse_args()

    opts = _opts(args.udid)
    drv = webdriver.Remote(args.appium, options=opts)
    try:
        # Decide nickname (ensure uniqueness across runs)
        nick = args.nickname or unique_nickname(args.name_style, args.unique_store)
        first_run_consent(drv)
        # If email is given, try to fill it before/after nickname as needed.
        if args.email:
            enter_email_if_present(drv, args.email)
        try_registration(drv, nick, gender=args.gender, age=args.age)
        if args.email:
            # Try tapping a generic submit/next button to trigger email verification
            tap_submit_if_present(drv)
        return 0
    finally:
        try:
            drv.quit()
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main())
