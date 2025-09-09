概要
- 目的: 「tengamax のような転売セラー」を広く発見するため、検索/カテゴリ/商品ページをシードにアイテムをサンプル→セラーを集計→典型語の出現率でスコア化するヒューリスティックツール。
- 方針: 公開HTMLの最小限取得＋タイトル中心の軽量判定。頻度/総量は抑制（delay有）。

使い方（CLI）
1) キーワードファイルから検索してセラー候補を抽出
```
echo 未塗装 > data/keywords.txt
echo 1/35 >> data/keywords.txt
echo TPE >> data/keywords.txt
python -m ytanalyzer.cli resale-find-sellers --keywords data/keywords.txt --pages-per-keyword 1 --out exports/seller_candidates.csv
```

2) 検索・カテゴリ等のURLをシードにして抽出
```
python -m ytanalyzer.cli resale-find-sellers --seed-urls data/seed_urls.txt --out exports/seller_candidates.csv
```

主なオプション
- `--sample-items-per-seller`: セラーごとのサンプル件数上限（既定5）
- `--total-item-cap`: 総サンプル上限（既定400）
- `--min-hit-rate`: 典型語のヒット率の閾値（既定0.2）
- `--top-k`: 出力上限（既定200）
 - `--min-overseas-rate`: 発送元が海外（推定）となった割合の閾値（既定0.5）
 - `--min-overseas`: 海外判定アイテムの必要最小個数（既定1）

出力
- CSV: `exports/seller_candidates.csv`
  - 列: `seller_id, seller_url, n_items_sample, title_hits, hit_rate, overseas_hits, overseas_rate, score, example_item_url, example_title`
  - スコア: ヒット率とサンプル件数からの簡易合成

典型語（初期値）
- 海外倉庫, 海外発送, 営業日, 通関, 7–20日, 10–30日, 未塗装, 未組立, レジン, Resin, figure, 1/35, for iPhone, Universal, TPE, PUレザー, BDSM, ほか
- `ytanalyzer/services/seller_finder.py` の `PHRASE_PATTERNS` を編集して調整できます。

注意
- Yahoo!側の規約/ヘルプに留意し、頻度・総量は控えめに。遮断兆候があれば即停止してください。
- HTML構造の変化により抽出ロジックの調整が必要になる可能性があります。

海外判定の仕組み（ヒューリスティック）
- 商品ページの「発送元の地域/発送元/配送元」などの表記から地域名を抽出し、`海外/中国/香港/台湾/USA/EU` 等の語で判定
- 「7–20日/10–30日/海外倉庫/通関/営業日」などの納期/テンプレの語を補助信号として使用
- 候補表示では `overseas_hits / overseas_rate` を付与し、`--min-overseas-rate` でフィルタ可能

次のステップ
- 確証強化: 各セラーから数件を `resale-mvp` でAE候補突き合わせ→確信度の高いフラグ付け。
- 特徴量追加: 納期/送料表現・カテゴリ分布・テンプレ文の検出。
- ダッシュボード: スコア順にセラー/証拠を一覧表示。
