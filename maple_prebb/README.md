Pre-BB Maple Crawler (Wayback-driven)

Quickstart

- Python 3.11+
- Ensure these deps are available (already in project requirements): requests, PyYAML, beautifulsoup4, lxml
- Optional for WARC and replay: warcio, pywb

Commands

- Crawl: `python -m maple_prebb crawl maple_prebb/seeds.example.yaml --limit 20`
- Crawl (JP Maple curated): `python -m maple_prebb crawl maple_prebb/seeds.maple_jp.yaml --limit 200`
- Search: `python -m maple_prebb search "メイプル 斬り賊" --year 2007`
- Replay (manual): `python -m maple_prebb replay`
- Replay (auto): `python -m maple_prebb replay --auto --warc-dir ./archive/warc --collection maple --port 8080`

Outputs

- WARC to ./archive/warc when warcio is installed. Otherwise raw files + JSON meta to ./archive/meta
- SQLite index at ./index/maple.db (FTS5 if available)

Install optional tools

- `pip install warcio pywb`
- Initialize replay manually:
  - `wb-manager init maple`
  - `wb-manager add maple "./archive/warc/*.warc*"`
  - `wayback --collections maple --host 127.0.0.1 --port 8080`

Config

- See maple_prebb/seeds.example.yaml. You can copy it to seeds.yaml and tweak sources/match/cdx options.
- For JP Maple pre‑BB focus, start with `maple_prebb/seeds.maple_jp.yaml`.
