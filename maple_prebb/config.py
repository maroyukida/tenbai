from __future__ import annotations

from pathlib import Path
from typing import Any, Dict
import yaml


def load_config(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    # Basic defaults
    data.setdefault("time_range", {"to": "20091231"})
    data.setdefault("fetch", {"rps": 1.5, "retries": 3, "timeout_sec": 20})
    data.setdefault("store", {"warc_dir": "./archive/warc", "meta_dir": "./archive/meta", "index": "./index/maple.db"})
    data.setdefault("cdx", {"collapse": "digest", "fields": ["timestamp", "original", "mimetype", "statuscode", "digest", "length"]})
    return data

