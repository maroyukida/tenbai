# YTAnalyzer v3 (from-scratch, fully modular)

新規�Eロジェクトとして全面再構築しつつ、旧 `you.py` / `ban.py` の実裁E��、E統合版 `scraper_v2.py`・`growth_service.py`・`ban_service.py` の要点を最大限引き継いだ構�Eです、E
## 主要機�E
- 🔎 **BAN収集**: yutura の BAN 一覧を巡回し、詳細から BAN 日付、登録老E��総�E生、最新動画の抜粋等を保孁E- 🧠 **AI刁E��E*: BAN 琁E��をルール + LLM(DeepSeek API) で刁E��！EPIキーは `.env` 経由�E�E- 📈 **成長刁E��**: スナップショチE��から成長玁Eスコア/トレンドを算�E
- 🌐 **Web UI**: 一覧�E�カーチEチE�Eブル�E�、タグフィルタ、詳細、統訁E刁E��、CSV/JSON エクスポ�EチE
## チE��レクトリ構�E
```
ytanalyzer_v3/
  ├─ ytanalyzer/
  ━E  ├─ __init__.py
  ━E  ├─ config.py
  ━E  ├─ db.py
  ━E  ├─ cli.py
  ━E  ├─ scrapers/
  ━E  ━E  ├─ __init__.py
  ━E  ━E  ├─ http.py
  ━E  ━E  ├─ yutura_ban.py
  ━E  ━E  └─ yutura_rankings.py
  ━E  ├─ services/
  ━E  ━E  ├─ __init__.py
  ━E  ━E  ├─ ban_service.py
  ━E  ━E  └─ growth_service.py
  ━E  ├─ webapp/
  ━E  ━E  ├─ __init__.py
  ━E  ━E  └─ app.py
  ━E  ├─ templates/
  ━E  ━E  ├─ layout.html
  ━E  ━E  ├─ index.html
  ━E  ━E  ├─ channel.html
  ━E  ━E  ├─ analytics.html
  ━E  ━E  └─ data_table.html
  ━E  └─ static/
  ├─ .env.example
  ├─ requirements.txt
  ├─ README.md
  └─ data/                 # SQLite�E�デフォルチE data/yutura.sqlite�E�E```

## セチE��アチE�E
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# .env を編雁E��て DeepSeek API KEY めECookie を設宁E```

## 使ぁE��

### 1) BANスクレイピング�E�一覧→詳細→最新動画抜粋�EDB保存！E```bash
python -m ytanalyzer.cli scrape   --start-page 1 --max-pages 50   --videos-per-channel 3   --db data/yutura.sqlite   --cookies-txt cookies.txt   --request-wait 0.45 --page-wait 1.2 --cooldown-429 90
```

### 2) Web UI 起勁E```bash
python -m ytanalyzer.cli serve --db data/yutura.sqlite --host 127.0.0.1 --port 8794
# http://127.0.0.1:8794
```

### 3) 成長刁E���E�例！E```bash
python -m ytanalyzer.cli growth-report --channel-id 12345 --days 30 --db data/yutura.sqlite
```

### 4) エクスポ�EチE- JSON: `/export.json`
- CSV : `/export.csv`

## 注愁E- yutura 側仕様変更によりセレクタは随時調整が忁E��です、E- スクレイピング対象の利用規紁Erobots.txt を�E守してください、E- 連続アクセス/429 を避けるためウェイトを忁E��設定してください、E- DeepSeek API キーは `.env` で設定してください。�Eレーンキーのハ�Eドコード�E禁止です、E
