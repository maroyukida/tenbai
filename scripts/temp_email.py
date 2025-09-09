from __future__ import annotations

import os
import re
import time
import json
import random
import string
from dataclasses import dataclass
from typing import Optional, Tuple

import requests


@dataclass
class TempMailbox:
    address: str
    password: Optional[str] = None
    provider: str = ""
    auth: Optional[dict] = None  # provider-specific


def _rand(n: int = 10) -> str:
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=n))


def create_mailbox_1secmail() -> TempMailbox:
    r = requests.get("https://www.1secmail.com/api/v1/", params={"action": "genRandomMailbox", "count": 1}, timeout=20)
    r.raise_for_status()
    addr = r.json()[0]
    return TempMailbox(address=addr, provider="1secmail")


def poll_message_1secmail(addr: str, timeout: int = 180, subject_hint: Optional[str] = None) -> Tuple[dict, str]:
    login, domain = addr.split("@", 1)
    end = time.time() + timeout
    while time.time() < end:
        r = requests.get("https://www.1secmail.com/api/v1/", params={"action": "getMessages", "login": login, "domain": domain}, timeout=20)
        r.raise_for_status()
        msgs = r.json() or []
        for m in msgs:
            if (subject_hint is None) or (subject_hint.lower() in (m.get("subject", "").lower())):
                mid = m.get("id")
                r2 = requests.get("https://www.1secmail.com/api/v1/", params={"action": "readMessage", "login": login, "domain": domain, "id": mid}, timeout=20)
                r2.raise_for_status()
                body = r2.json()
                html = body.get("htmlBody") or body.get("textBody") or ""
                return body, html
        time.sleep(3)
    raise TimeoutError("Timeout waiting for email on 1secmail")


def create_mailbox_mailtm() -> TempMailbox:
    s = requests.Session()
    base = os.environ.get("MAILTM_BASE", "https://api.mail.tm")
    r = s.get(f"{base}/domains", timeout=20)
    r.raise_for_status()
    items = r.json().get("hydra:member", [])
    if not items:
        raise RuntimeError("mail.tm domains not available")
    domain = random.choice(items)["domain"]
    addr = f"{_rand(7)}{int(time.time())}@{domain}"
    pwd = _rand(14)
    r = s.post(f"{base}/accounts", json={"address": addr, "password": pwd}, timeout=20)
    # 201 created or 409 if already exists
    if r.status_code not in (200, 201, 409):
        raise RuntimeError(f"mail.tm account create failed: {r.status_code} {r.text}")
    r = s.post(f"{base}/token", json={"address": addr, "password": pwd}, timeout=20)
    r.raise_for_status()
    token = r.json().get("token")
    s.headers.update({"Authorization": f"Bearer {token}"})
    return TempMailbox(address=addr, password=pwd, provider="mailtm", auth={"session": s, "base": base})


def poll_message_mailtm(box: TempMailbox, timeout: int = 180, subject_hint: Optional[str] = None) -> Tuple[dict, str]:
    s: requests.Session = box.auth["session"]
    base: str = box.auth["base"]
    end = time.time() + timeout
    while time.time() < end:
        r = s.get(f"{base}/messages", timeout=20)
        r.raise_for_status()
        for m in r.json().get("hydra:member", []):
            sub = (m.get("subject") or "").lower()
            if (subject_hint is None) or (subject_hint.lower() in sub):
                mid = m.get("id")
                r2 = s.get(f"{base}/messages/{mid}", timeout=20)
                r2.raise_for_status()
                msg = r2.json()
                html = msg.get("html") or msg.get("text") or ""
                return msg, html
        time.sleep(3)
    raise TimeoutError("Timeout waiting for email on mail.tm")


URL_RE = re.compile(r"https?://[\w\-\._~:/?#\[\]@!$&'()*+,;=%]+", re.I)


def first_url_from_html(html: str, host_hint: Optional[str] = None) -> Optional[str]:
    for m in URL_RE.finditer(html or ""):
        url = m.group(0)
        if (host_hint is None) or (host_hint.lower() in url.lower()):
            return url
    return None


def create_mailbox(provider: str = "1secmail") -> TempMailbox:
    provider = provider.lower()
    if provider == "1secmail":
        return create_mailbox_1secmail()
    if provider == "mailtm":
        return create_mailbox_mailtm()
    raise ValueError(f"Unsupported provider: {provider}")


def poll_message(box: TempMailbox, timeout: int = 180, subject_hint: Optional[str] = None) -> Tuple[dict, str]:
    if box.provider == "1secmail":
        return poll_message_1secmail(box.address, timeout=timeout, subject_hint=subject_hint)
    if box.provider == "mailtm":
        return poll_message_mailtm(box, timeout=timeout, subject_hint=subject_hint)
    raise ValueError(f"Unsupported provider: {box.provider}")

