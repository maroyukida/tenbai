from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional
import gzip
import json
import time

from .fetch import FetchResponse


class WarcOrFolderWriter:
    """
    Write responses into WARC if warcio is available; otherwise store as files under meta_dir.
    """

    def __init__(self, warc_dir: Path, meta_dir: Path):
        self.warc_dir = warc_dir
        self.meta_dir = meta_dir
        self._warcio = None
        try:
            from warcio.warcwriter import WARCWriter  # type: ignore
            from io import BytesIO  # noqa: F401
            self._warcio = WARCWriter
        except Exception:
            self._warcio = None

    def write(self, row: Dict[str, str], response: FetchResponse) -> Dict[str, Optional[Path]]:
        ts = row.get("timestamp") or str(int(time.time()))
        digest = row.get("digest") or "nodigest"
        original = row.get("original") or response.url

        if self._warcio:
            return self._write_warc(ts=ts, original=original, response=response)
        else:
            return self._write_folder(ts=ts, digest=digest, original=original, response=response)

    def _write_folder(self, ts: str, digest: str, original: str, response: FetchResponse) -> Dict[str, Optional[Path]]:
        # save content
        base = f"{ts}_{digest}"
        content_path = self.meta_dir / f"{base}.bin"
        metadata_path = self.meta_dir / f"{base}.json"
        content_path.write_bytes(response.content)
        metadata = {
            "original": original,
            "wayback_url": response.url,
            "timestamp": ts,
            "status": response.status_code,
            "headers": response.headers,
            "content_path": str(content_path),
        }
        metadata_path.write_text(json.dumps(metadata, ensure_ascii=False), encoding="utf-8")
        return {"warc_path": None, "meta_path": metadata_path}

    def _write_warc(self, ts: str, original: str, response: FetchResponse) -> Dict[str, Optional[Path]]:
        # Lazy, simple WARC file per day
        day = ts[:8]
        warc_path = self.warc_dir / f"maple_{day}.warc.gz"
        from io import BytesIO
        from warcio.warcwriter import WARCWriter
        from warcio.statusandheaders import StatusAndHeaders

        warc_path.parent.mkdir(parents=True, exist_ok=True)
        # Append to gz file
        with warc_path.open("ab") as stream:
            writer = WARCWriter(stream, gzip=True)

            http_headers = StatusAndHeaders(
                f"{response.status_code} OK",
                list(response.headers.items()),
                protocol="HTTP/1.1",
            )

            record = writer.create_warc_record(
                original,
                "response",
                payload=BytesIO(response.content),
                http_headers=http_headers,
            )
            writer.write_record(record)

        return {"warc_path": warc_path, "meta_path": None}
