HeavenMS v83 — World Select が白い・リストが出ない時の実践手順

概要
- 症状: ワールド選択画面に吹き出し等は出るが、ワールド一覧が表示されない/真っ白
- 典型原因: 
  - Server 未登録（ChannelがWorldに登録されていない、ポート未LISTEN）
  - 接続先不一致（IPv6/localhost解決のズレ。127.0.0.1に固定されていない）
  - クライアント側（WZ/互換レイヤ）不整合（UI.wz の WorldSelect 要素、dinput8不在 等）

最短フロー
1) 診断スクリプトを実行して状況を把握
   - PowerShell: 
     - `Set-ExecutionPolicy -Scope Process Bypass -Force`
     - `./scripts/heavenms_diag.ps1 -ServerRoot "C:\\HeavenMS" -ClientRoot "C:\\MapleV83"`
   - 出力: `scripts/heavenms_diag_output.txt`

2) サーバ側の前提を満たす
   - すべてのバインドIPは `127.0.0.1` に統一
   - Login: 8484 LISTEN、Channel: 7575+ LISTEN を確認
   - 起動ログに `Registered channel` の行が出ていること

3) クライアントの接続先と互換性
   - 接続IP: `127.0.0.1`（localhostではなく明示）
   - 管理者権限、互換モード XP(SP3)、高DPIスケーリング「アプリケーション」
   - `dinput8.dll` を MapleStory.exe と同じフォルダに配置

4) WZ 不整合の切り分け
   - まず `UI.wz` を既知良品 v83 に置換（混在を避ける）
   - 変化が無ければ `Etc.wz`, `String.wz`, `Map.wz` も同一配布元の v83 に統一

ヒント
- 吹き出しやOK/Cancelは出るのにリストが空 → クライアント(WZ/互換)の可能性が高い
- 8484/7575 が LISTEN していない → サーバ起動順 or IPバインド設定を確認
- IPv6 が優先される環境で `localhost` は避ける（127.0.0.1 を直接指定）

よくある設定例（サーバ側）
- `HOST`/`PUBLIC_IP`: `127.0.0.1`
- `PORT_LOGIN=8484`, `PORT_CHANNEL_BASE=7575`, `CHANNELS >= 1`
- `FLAG=0`（メンテ表示を避ける）

それでも解消しない場合
- `scripts/heavenms_diag_output.txt` を共有すれば、原因箇所を特定し次の修正を提示できます。

