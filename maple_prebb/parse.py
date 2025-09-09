from __future__ import annotations

from typing import Optional, Tuple

from bs4 import BeautifulSoup


def _try_decode(b: bytes, enc: str) -> Optional[str]:
    try:
        return b.decode(enc)
    except Exception:
        return None


PREFERRED_ENCODINGS = ["utf-8", "cp932", "euc-jp", "iso-2022-jp"]


def extract_text_and_title(content: bytes) -> Tuple[str, str, Optional[str]]:
    text: Optional[str] = None
    used_charset: Optional[str] = None
    for enc in PREFERRED_ENCODINGS:
        s = _try_decode(content, enc)
        if s is not None:
            text = s
            used_charset = enc
            break
    if text is None:
        # Fallback with replacement to avoid crashes
        text = content.decode("utf-8", errors="replace")
        used_charset = None

    soup = BeautifulSoup(text, "lxml")
    # Title
    title = soup.title.string.strip() if soup.title and soup.title.string else ""
    # Rough text extraction
    for s in soup(["script", "style", "noscript"]):
        s.decompose()
    body_text = soup.get_text(" ")
    body_text = " ".join(body_text.split())
    return body_text, title, used_charset

