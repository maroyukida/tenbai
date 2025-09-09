簡単セットアップ（Windows）

1) 画像を自動生成（ダミー）
- `himachat-mobile/generate_assets.bat` を実行
- `assets/icon.png` と `assets/splash.png` が作成されます（後で差し替え可能）

2) Firebase構成値を入力
- `himachat-mobile/config_firebase.bat` を実行し、コンソールの質問に答えて `app.json` を更新

3) 公開前チェック
- `himachat-mobile/preflight.bat` を実行
- すべて ✓ になればOK（✗ が出た項目を埋めて再実行）

4) 起動/検証
- クラウド接続: `start_web.bat`（Web）/ `start_android.bat`（Android）
- エミュ接続: `emu_start.bat` → `start_web_emulator.bat` または `start_android_emulator.bat`

5) ビルド
- 内部配布: `build_android_preview.bat`

