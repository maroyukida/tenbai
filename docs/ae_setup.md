AliExpress API キー取得と接続手順（最短）

1) Portals（アフィリエイト）で tracking_id を取得
- 開く: https://portals.aliexpress.com/affiportals/web/portals.htm#/home
- 申請→承認→ダッシュボードでトラッキングID（PID/adzoneId/tracking_id）を作成
- これを `.env` の `ALIEXPRESS_TRACKING_ID` に設定

用途説明（例・貼り付け可）
商品レビュー／比較紹介用の情報サイト・SNSでAliExpress商品を紹介します。規約と法令を順守し、スパム行為は行いません。

2) Open Platform（開発者）で App Key/Secret を発行
- 開く: https://open.aliexpress.com → Console → My Apps → Create App
- 種別: Server（推奨）
- 権限/製品: Portals/Affiliate API（バインド必須）
- 発行された `App Key` / `App Secret` を控え、`.env` に設定

3) プロジェクトの `.env` を設定
`.env.example` を参考に `.env` を作成し、以下を記入:
- `ALIEXPRESS_APP_KEY=...`
- `ALIEXPRESS_APP_SECRET=...`
- `ALIEXPRESS_TRACKING_ID=...`

4) 疎通テスト（CLI）
1) 依存インストール: `pip install -r requirements.txt`
2) キーテスト: `python -m ytanalyzer.cli resale-ae-check --q "iphone case" --n 3`
   - ID/タイトル/価格/URL が表示されれば接続OK

5) 「転売ヤーだけ」検証を実行
候補→検証の順で実行し、AE一致/高スコア/利益ありで絞込。
- 候補探索（例）: `python -m ytanalyzer.cli resale-find-sellers --keywords data/keywords.txt --pages-per-keyword 2 --per-page 50 --total-item-cap 200 --out exports/seller_candidates.csv`
- 検証＆絞込: `python -m ytanalyzer.cli resale-verify-sellers --inp exports/seller_candidates.csv --out exports/seller_verified.csv --sellers 50 --items-per-seller 3 --score-threshold 0.75 --matched-only --min-high 1 --item-min-score 0.75 --item-min-profit 0`
- Web確認: `/resale/verified` と `/resale/items` を表示

トラブル対処
- 403/署名エラー: Key/Secret/TrackingID が誤っている、Affiliate権限未付与、PC時刻ズレ
- 0件しか返らない: Portals API の権限バインド未完了、地域制限
- 通貨がUSD: `.env` の `FX_USDJPY` を調整（既定 155.0）
