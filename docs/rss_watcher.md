RSS ウォッチャ（新着検出 / 13万ch 想定）

依存（追加）
- httpx[http2]
- feedparser

インストール
```
pip install -r requirements.txt
```

小規模テスト（2000件・安全なRPSで）
```
python -m ytanalyzer.cli rss-watch \
  --channels-file C:\\Users\\mouda\\Documents\\yutura\\yutura_channels.ndjson \
  --once --limit 2000 --rps 10
```

常駐実行（例。回線/マシンに合わせて調整）
```
python -m ytanalyzer.cli rss-watch \
  --channels-file C:\\Users\\mouda\\Documents\\yutura\\yutura_channels.ndjson \
  --concurrency 200 --rps 15 --batch 800 --tick 5
```

進捗ダッシュボード
- ルート直下の `rss_dashboard.html` を使い、`data/rss_progress.json` を5秒ごとに読み込みます。
```
python -m http.server 8000
# ブラウザ: http://localhost:8000/rss_dashboard.html
```

備考
- RSS は「新着検出」に専念。検出済みIDを API 側の後続処理に渡してください。
- ETag/Last-Modified・指数バックオフ・RPS 制御で安定運用できます。

