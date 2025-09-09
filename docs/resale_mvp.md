概要
- 目的: ヤフオクの商品（URLまたはセラー一覧）を取得し、AliExpressの同一/類似商品候補と照合して「転売っぽさ」をスコア化する最小プロトタイプ（MVP）。
- 注意: 公開Webの規約を順守してください。頻度/量を抑え、フェイルセーフ（停止条件・ログ）を用意してください。AliExpress側は公式API利用を推奨します。

実行に必要なもの
- Python依存関係: `requirements.txt`（Pillow, ImageHash 追加済）
- 任意（推奨）: AliExpress公式APIの認証情報
  - 環境変数 `ALIEXPRESS_APP_KEY`, `ALIEXPRESS_APP_SECRET`, `ALIEXPRESS_TRACKING_ID`
  - これらが未設定の場合は、AE候補検索はスキップされ、CSVに `no_ae_candidates` と記録されます。

使い方（CLI）
1) URLリストを用意して突き合わせ
```
python -m ytanalyzer.cli resale-mvp --input-urls data/yahoo_items.txt --out exports/resale_candidates.csv
```

2) セラーページから数ページ分をクロールして突き合わせ
```
python -m ytanalyzer.cli resale-mvp --seller-url "https://auctions.yahoo.co.jp/seller/XXXXX?user_type=c" --seller-pages 2 --out exports/resale_candidates.csv
```

オプション
- `--per-item-candidates` (int): AliExpress側で各商品に対して取得する候補数（既定3）
- `--delay-min`, `--delay-max` (float): 取得間隔のランダムウェイト（既定 1.2〜2.2 秒）

出力
- CSV: `exports/resale_candidates.csv`
  - 主な列: `yahoo_url, yahoo_title, yahoo_price, yahoo_image, ae_url, ae_title, ae_price, ae_image, title_sim, img_dist, price_ratio, score, error`
  - `score`: 画像類似（pHash）/タイトル類似/価格比からの簡易スコア（チューニング前提）
  - `error`: 失敗・候補無しなどの理由を格納

制限・補足
- Yahoo側のHTML構造は変更されることがあります。セレクタは随時調整してください。
- AE検索は公式APIラッパー（`python-aliexpress-api`）に依存します（インストールしていない場合も動作はしますが、候補は取得しません）。
- 画像ハッシュ（pHash）は `Pillow` と `ImageHash` を使用。未導入/失敗時は画像類似度は無効になります。

次のステップ（改善案）
- Yahoo側の抽出強化: JSON-LD/構造化データの解析、価格・送料の正規化。
- AE候補の拡充: タイトル正規化（型番/属性の抽出）、マルチクエリ（英語化）でRecall向上。
- 画像類似の強化: pHash + ORB/SURF等の局所特徴の併用。
- セラー単位スコア: 高スコア出品の割合、価格比分布、納期表現の辞書化による特徴量追加。
- ダッシュボード化: 左右並置ビュー、証拠（ハイライト/類似度）を可視化、CSV/PDFエクスポート。

法務まわりのメモ（一般論）
- 自動取得の禁止・制限があるサイトでは、規約・ヘルプの確認が必須です。
- アクセス頻度の抑制、キャッシュ、遮断兆候時の停止、ログの保持（監査）を推奨します。
