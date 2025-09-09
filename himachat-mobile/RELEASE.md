Pocchari Chat リリース前チェックリスト（Android/iOS）

1) アセット/メタデータ
- アイコン: `assets/icon.png`（1024x1024）
- スプラッシュ: `assets/splash.png`（推奨 1242x2436 以上）
- `app.json` を編集:
  - `expo.name`, `expo.slug`
  - `expo.version`（例: 1.0.0）
  - `expo.android.package`（例: com.yourorg.poccharichat）と `expo.android.versionCode`（整数）
  - `expo.ios.bundleIdentifier` と `expo.ios.buildNumber`

2) Firebase
- Authentication: Anonymous を有効化
- Firestore: 有効化＆ `firestore.rules` を公開
- Admin: Firestoreに `admins/{あなたのUID}` を作成（通報管理用）

3) アプリの必須確認
- 初回起動→「利用規約」に同意できること（Terms画面）
- マッチング→チャット（送受信/入力中表示）
- 退室→再マッチが可能
- プロフィール→ニックネーム変更、ブロック/解除
- 退会（データ削除）→再起動で新しい匿名ユーザーとして起動
- 通報→管理画面にレポート表示、部屋停止/メッセ削除

4) 内部配布ビルド（EAS）
- `cd himachat-mobile`
- 初回のみ: `npx expo login`
- Android: `build_android_preview.bat`（AABを作成）
- iOS（オプション）: `npx eas build -p ios --profile preview`

5) ストア提出（概要）
- Android: Google Play Console でアプリ作成→AABアップロード→審査
- iOS: App Store Connect でアプリ作成→TestFlight/審査
- ストア審査用テキスト: プライバシーポリシーURL、スクリーンショット、説明文

注意
- 本MVPは最小ルール/モデレーションです。公開範囲やスパム状況に応じて強化を検討してください。
- 不具合時は Firebase Emulator モード（`start_web_emulator.bat` など）で再現/切り分けが便利です。

