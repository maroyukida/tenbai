# YTAnalyzer v3 (from-scratch, fully modular)

譁ｰ隕上・繝ｭ繧ｸ繧ｧ繧ｯ繝医→縺励※蜈ｨ髱｢蜀肴ｧ狗ｯ峨＠縺､縺､縲∵立 `you.py` / `ban.py` 縺ｮ螳溯｣・→縲・邨ｱ蜷育沿 `scraper_v2.py`繝ｻ`growth_service.py`繝ｻ`ban_service.py` 縺ｮ隕∫せ繧呈怙螟ｧ髯仙ｼ輔″邯吶＞縺讒区・縺ｧ縺吶・
## 荳ｻ隕∵ｩ溯・
- 博 **BAN蜿朱寔**: yutura 縺ｮ BAN 荳隕ｧ繧貞ｷ｡蝗槭＠縲∬ｩｳ邏ｰ縺九ｉ BAN 譌･莉倥∫匳骭ｲ閠・∫ｷ丞・逕溘∵怙譁ｰ蜍慕判縺ｮ謚懃ｲ狗ｭ峨ｒ菫晏ｭ・- ｧ **AI蛻・｡・*: BAN 逅・罰繧偵Ν繝ｼ繝ｫ + LLM(DeepSeek API) 縺ｧ蛻・｡橸ｼ・PI繧ｭ繝ｼ縺ｯ `.env` 邨檎罰・・- 嶋 **謌宣聞蛻・梵**: 繧ｹ繝翫ャ繝励す繝ｧ繝・ヨ縺九ｉ謌宣聞邇・繧ｹ繧ｳ繧｢/繝医Ξ繝ｳ繝峨ｒ邂怜・
- 倹 **Web UI**: 荳隕ｧ・医き繝ｼ繝・繝・・繝悶Ν・峨√ち繧ｰ繝輔ぅ繝ｫ繧ｿ縲∬ｩｳ邏ｰ縲∫ｵｱ險・蛻・梵縲，SV/JSON 繧ｨ繧ｯ繧ｹ繝昴・繝・
## 繝・ぅ繝ｬ繧ｯ繝医Μ讒区・
```
ytanalyzer_v3/
  笏懌楳 ytanalyzer/
  笏・  笏懌楳 __init__.py
  笏・  笏懌楳 config.py
  笏・  笏懌楳 db.py
  笏・  笏懌楳 cli.py
  笏・  笏懌楳 scrapers/
  笏・  笏・  笏懌楳 __init__.py
  笏・  笏・  笏懌楳 http.py
  笏・  笏・  笏懌楳 yutura_ban.py
  笏・  笏・  笏披楳 yutura_rankings.py
  笏・  笏懌楳 services/
  笏・  笏・  笏懌楳 __init__.py
  笏・  笏・  笏懌楳 ban_service.py
  笏・  笏・  笏披楳 growth_service.py
  笏・  笏懌楳 webapp/
  笏・  笏・  笏懌楳 __init__.py
  笏・  笏・  笏披楳 app.py
  笏・  笏懌楳 templates/
  笏・  笏・  笏懌楳 layout.html
  笏・  笏・  笏懌楳 index.html
  笏・  笏・  笏懌楳 channel.html
  笏・  笏・  笏懌楳 analytics.html
  笏・  笏・  笏披楳 data_table.html
  笏・  笏披楳 static/
  笏懌楳 .env.example
  笏懌楳 requirements.txt
  笏懌楳 README.md
  笏披楳 data/                 # SQLite・医ョ繝輔か繝ｫ繝・ data/yutura.sqlite・・```

## 繧ｻ繝・ヨ繧｢繝・・
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# .env 繧堤ｷｨ髮・＠縺ｦ DeepSeek API KEY 繧・Cookie 繧定ｨｭ螳・```

## 菴ｿ縺・婿

### 1) BAN繧ｹ繧ｯ繝ｬ繧､繝斐Φ繧ｰ・井ｸ隕ｧ竊定ｩｳ邏ｰ竊呈怙譁ｰ蜍慕判謚懃ｲ銀・DB菫晏ｭ假ｼ・```bash
python -m ytanalyzer.cli scrape   --start-page 1 --max-pages 50   --videos-per-channel 3   --db data/yutura.sqlite   --cookies-txt cookies.txt   --request-wait 0.45 --page-wait 1.2 --cooldown-429 90
```

### 2) Web UI 襍ｷ蜍・```bash
python -m ytanalyzer.cli serve --db data/yutura.sqlite --host 127.0.0.1 --port 8794
# http://127.0.0.1:8794
```

### 3) 謌宣聞蛻・梵・井ｾ具ｼ・```bash
python -m ytanalyzer.cli growth-report --channel-id 12345 --days 30 --db data/yutura.sqlite
```

### 4) 繧ｨ繧ｯ繧ｹ繝昴・繝・- JSON: `/export.json`
- CSV : `/export.csv`

## 豕ｨ諢・- yutura 蛛ｴ莉墓ｧ伜､画峩縺ｫ繧医ｊ繧ｻ繝ｬ繧ｯ繧ｿ縺ｯ髫乗凾隱ｿ謨ｴ縺悟ｿ・ｦ√〒縺吶・- 繧ｹ繧ｯ繝ｬ繧､繝斐Φ繧ｰ蟇ｾ雎｡縺ｮ蛻ｩ逕ｨ隕冗ｴ・robots.txt 繧帝・螳医＠縺ｦ縺上□縺輔＞縲・- 騾｣邯壹い繧ｯ繧ｻ繧ｹ/429 繧帝∩縺代ｋ縺溘ａ繧ｦ繧ｧ繧､繝医ｒ蠢・★險ｭ螳壹＠縺ｦ縺上□縺輔＞縲・- DeepSeek API 繧ｭ繝ｼ縺ｯ `.env` 縺ｧ險ｭ螳壹＠縺ｦ縺上□縺輔＞縲ゅ・繝ｬ繝ｼ繝ｳ繧ｭ繝ｼ縺ｮ繝上・繝峨さ繝ｼ繝峨・遖∵ｭ｢縺ｧ縺吶・
