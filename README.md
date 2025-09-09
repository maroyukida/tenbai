# YTAnalyzer v3 (from-scratch, fully modular)

新規プロジェクトとして全面再構築しつつ、旧 `you.py` / `ban.py` の実装と、
統合版 `scraper_v2.py`・`growth_service.py`・`ban_service.py` の要点を最大限引き継いだ構成です。

## 主要機能
- 🔎 **BAN収集**: yutura の BAN 一覧を巡回し、詳細から BAN 日付、登録者、総再生、最新動画の抜粋等を保存
- 🧠 **AI分類**: BAN 理由をルール + LLM(DeepSeek API) で分類（APIキーは `.env` 経由）
- 📈 **成長分析**: スナップショットから成長率/スコア/トレンドを算出
- 🌐 **Web UI**: 一覧（カード/テーブル）、タグフィルタ、詳細、統計/分析、CSV/JSON エクスポート

## ディレクトリ構成
```
ytanalyzer_v3/
  ├─ ytanalyzer/
  │   ├─ __init__.py
  │   ├─ config.py
  │   ├─ db.py
  │   ├─ cli.py
  │   ├─ scrapers/
  │   │   ├─ __init__.py
  │   │   ├─ http.py
  │   │   ├─ yutura_ban.py
  │   │   └─ yutura_rankings.py
  │   ├─ services/
  │   │   ├─ __init__.py
  │   │   ├─ ban_service.py
  │   │   └─ growth_service.py
  │   ├─ webapp/
  │   │   ├─ __init__.py
  │   │   └─ app.py
  │   ├─ templates/
  │   │   ├─ layout.html
  │   │   ├─ index.html
  │   │   ├─ channel.html
  │   │   ├─ analytics.html
  │   │   └─ data_table.html
  │   └─ static/
  ├─ .env.example
  ├─ requirements.txt
  ├─ README.md
  └─ data/                 # SQLite（デフォルト: data/yutura.sqlite）
```

## セットアップ
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# .env を編集して DeepSeek API KEY や Cookie を設定
```

## 使い方

### 1) BANスクレイピング（一覧→詳細→最新動画抜粋→DB保存）
```bash
python -m ytanalyzer.cli scrape   --start-page 1 --max-pages 50   --videos-per-channel 3   --db data/yutura.sqlite   --cookies-txt cookies.txt   --request-wait 0.45 --page-wait 1.2 --cooldown-429 90
```

### 2) Web UI 起動
```bash
python -m ytanalyzer.cli serve --db data/yutura.sqlite --host 127.0.0.1 --port 8794
# http://127.0.0.1:8794
```

### 3) 成長分析（例）
```bash
python -m ytanalyzer.cli growth-report --channel-id 12345 --days 30 --db data/yutura.sqlite
```

### 4) エクスポート
- JSON: `/export.json`
- CSV : `/export.csv`

## 注意
- yutura 側仕様変更によりセレクタは随時調整が必要です。
- スクレイピング対象の利用規約/robots.txt を遵守してください。
- 連続アクセス/429 を避けるためウェイトを必ず設定してください。
- DeepSeek API キーは `.env` で設定してください。プレーンキーのハードコードは禁止です。

