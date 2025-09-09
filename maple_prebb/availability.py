from __future__ import annotations

import json
import urllib.parse
import urllib.request
from typing import Optional, Tuple, Dict, Any


AVAIL = "https://archive.org/wayback/available"


def availability(original_url: str, timestamp: str = "20091231") -> Optional[Dict[str, Any]]:
    qs = urllib.parse.urlencode({"url": original_url, "timestamp": timestamp})
    url = f"{AVAIL}?{qs}"
    with urllib.request.urlopen(url, timeout=30) as resp:
        raw = resp.read()
    data = json.loads(raw)
    closest = (data.get("archived_snapshots") or {}).get("closest")
    if closest and closest.get("available"):
        return closest
    return None

