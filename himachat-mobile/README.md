HimaChat モバイル MVP（Expo + Firebase）

概要
- 匿名ログイン、ランダム1対1マッチング、日本語UIの最小構成です。
- 技術: Expo(React Native) + Firebase（Auth 匿名 / Firestore）

セットアップ手順
1) Firebase プロジェクト作成
   - Authentication > Sign-in method で Anonymous を有効化
   - Firestore を有効化（リージョンはお好みで）

2) Firebase の Web アプリを追加し、構成（apiKey など）を取得

3) himachat-mobile/app.json の `expo.extra.firebase` を埋める
   ```json
   {
     "expo": {
       "extra": {
         "firebase": {
           "apiKey": "...",
           "authDomain": "...",
           "projectId": "...",
           "storageBucket": "...",
           "messagingSenderId": "...",
           "appId": "..."
         }
       }
     }
   }
   ```

4) 依存関係のインストール（PCに Node.js が必要）
   ```bash
   cd himachat-mobile
   npm install
   # Expo SDK とペアのパッケージは後で expo が補正します
   ```

5) 実行
   ```bash
   npx expo start
   ```
   - iOS/Android 実機またはエミュレータで動作確認

Firestore ざっくり構成
- collections
  - queue: マッチ待機行列（docId = uid）
    - { uid, status: 'waiting'|'matched', roomId?, createdAt }
  - rooms: チャットルーム
    - { participants: [uid1, uid2], createdAt, active: true }
    - subcollection messages: { text, senderId, createdAt }
    - subcollection presence: { lastActive }
  - reports: 通報レポート

最低限のセキュリティルール（参考・本番では強化推奨）
```javascript
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    function isSignedIn() { return request.auth != null; }
    function isRoomMember(roomId) {
      return exists(/databases/$(database)/documents/rooms/$(roomId)) &&
             request.auth.uid in get(/databases/$(database)/documents/rooms/$(roomId)).data.participants;
    }

    match /queue/{uid} {
      allow read, write: if isSignedIn() && uid == request.auth.uid;
    }

    match /rooms/{roomId} {
      allow read: if isSignedIn() && isRoomMember(roomId);
      allow write: if isSignedIn() && isRoomMember(roomId);
      match /messages/{msgId} {
        allow read, write: if isSignedIn() && isRoomMember(roomId);
      }
      match /presence/{memberId} {
        allow read, write: if isSignedIn() && (isRoomMember(roomId) && memberId == request.auth.uid);
      }
    }

    match /reports/{id} {
      allow create: if isSignedIn();
      allow read, update, delete: if false;
    }
  }
}
```

機能
- 匿名ログイン（自動）
- マッチング: 最古の待機者と1:1で即時ペアリング（衝突防止の簡易トランザクション対応）
  - チャット: テキスト送受信、既定の100件読み込み
  - プレゼンス: 心拍で lastActive を更新、30秒以内なら「オンライン」表示
  - 通報/ブロック: 通報は reports に記録（ブロックはローカル/簡易）
  - 退室: チャット画面左上「退室」で部屋を終了（active:false）し、自分の待機を掃除（次回は新規マッチ）

モデレーション（簡易）
- 送信制限: 1.5秒クールダウン（連投防止）
- 文字数: 最大300文字（UI）。ルール側で500文字上限も設定
- NGワード: `src/config.ts` の `NG_WORDS` で定義（ローカル判定）

運用まわり
- 自動クリーンアップ: 最終メッセージから10分以上無活動の部屋は、次回マッチングの前処理で `active:false` に自動切替（`findMatchOrEnqueue` 冒頭の `cleanupStaleRooms`）
- タイピング表示: `rooms/{roomId}/typing/{uid}` を更新・監視して「（入力中…）」を表示

プロフィール/ブロック
- profiles/{uid}: { nickname, blocked[] }
- 右上「プロフィール」からニックネーム編集とブロック一覧の解除
- チャット中のメニューから相手をブロック可能（以後のマッチング除外）

補足
- 本実装はMVP向けの簡易版です。スパム対策、連投抑制、NGワード、利用制限などは今後強化可能です。

管理者モード（任意）
- 管理者用コレクション: Firestoreで `admins` を作成し、あなたのUIDのドキュメントを1件作成（例: `admins/{あなたのUID}`）。この操作はFirebase Consoleで手動作成してください。
- ルール: `firestore.rules` に管理者判定（`isAdmin()`）を追加済み。管理者は `reports` の閲覧・削除、`rooms` の停止（`active: false`）や `messages` の削除が可能です。
- 画面:
  - `AdminReports`（通報一覧）: `管理` → 通報の部屋を開く/停止
  - `AdminRoom`（部屋の中身）: メッセージ個別削除
- アクセス: トップ右上に「管理」ボタンが表示されます（管理者UIDでログイン時のみ）。
