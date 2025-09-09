MuMu + Koetomo 自動化（下ごしらえ）

概要
- MuMu Manager (CLI) を使って新規インスタンス作成→起動→ADB 接続。
- その後、以下の2通りで Koetomo を導入。
  1) APK サイドロード（Play ストアログイン不要）
  2) Appium で Play ストアにログインしインストール（要 GOOGLE_EMAIL/PASSWORD）

前提
- MuMu Player Global 12 がインストール済み（`C:\Program Files\Netease\MuMuPlayerGlobal-12.0`）。
- Python + Appium-Python-Client（Appium サーバは 4725 で起動を想定）。

手順例
1) 新規インスタンス作成～起動～ADB 接続～APK サイドロード

```
powershell -ExecutionPolicy Bypass -File scripts/mumu_koetomo_setup.ps1 -CreateNew -KoetomoApk "C:\path\jp.co.meetscom.koetomo.apk"
```

2) 新規インスタンス作成～起動～Play ストアからインストール（Appium 使用）

```
$env:GOOGLE_EMAIL = "you@example.com"
$env:GOOGLE_PASSWORD = "your-password"
powershell -ExecutionPolicy Bypass -File scripts/mumu_koetomo_setup.ps1 -CreateNew -UsePlayStore -AppiumUrl "http://localhost:4725/wd/hub"

# Play ストア UI を Appium で操作してインストール（自動サインインヘルパ含む）
python scripts/playstore_install_koetomo.py --udid 127.0.0.1:16672 --appium http://localhost:4725/wd/hub
```

3) Koetomo 初回起動～（暫定）新規登録フロー雛形

```
python scripts/koetomo_register.py --udid 127.0.0.1:16672 --appium http://localhost:4725/wd/hub --nickname neko
```

4) メール認証の自動化（使い捨てメールを利用）

```
# まずは使い捨てメールを発行し、そのアドレスでアプリ内から認証メールを送信
python scripts/verify_koetomo_email.py --udid 127.0.0.1:16672 --provider 1secmail --subject-hint koetomo

# 実行開始後に表示される TEMP_EMAIL: のアドレスを Koetomo の登録画面に入力して送信
# スクリプトは受信箱をポーリングし、本文から最初のURLを抽出してエミュレータ内で開きます
```

4.1) iCloud+「メールを非公開」(Hide My Email) を使う場合（推奨）

- iCloud+でエイリアスを作成（例: `random_xxx@icloud.com`）。
- Apple IDで「アプリ用パスワード」を発行。
- IMAPで受信をポーリングして検証URLを開く:

```
setx IC_USER your_icloud_login@icloud.com
setx IC_APP_PASS abcd-efgh-ijkl-mnop   # Apple ID > セキュリティ > アプリ用パスワード

python scripts/verify_email_imap.py \
  --udid 127.0.0.1:16672 \
  --host imap.mail.me.com \
  --user %IC_USER% \
  --app-pass %IC_APP_PASS% \
  --to random_xxx@icloud.com \
  --subject koetomo \
  --timeout 900
```

- Koetomoの登録画面へは `scripts/koetomo_register.py` または `scripts/koetomo_full_register.py` でメールを投入。

5) APK 情報の確認

```
python scripts/apk_info.py "E:\\path\\app.apk"
```

備考
- `scripts/mumu_koetomo_setup.ps1` は MuMuManager の `create`/`control launch`/`adb connect` を使用。起動完了待ち・UDID 取得まで自動で行います。
- Play ストアの UI はバージョン・言語で変動が大きいため、`scripts/playstore_install_koetomo.py` のロケータは調整前提です（2FA が有効だと人手対応が必要な場合あり）。
- Koetomo の新規登録 UI も変更されやすいため、`scripts/koetomo_register.py` は雛形です。実機の文言に合わせて XPath を差し替えてください。
- 使い捨てメール（1secmail/mail.tm）は一部サービスでブロックされる可能性があります。確実性重視なら自前ドメイン + 受信API（Mailgun/SES等）や Gmail のエイリアス（+addressing）をご検討ください（ただし新規Gmail作成の自動化は非推奨・多くの場合規約/人間検証あり）。
