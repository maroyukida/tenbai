@echo off
title Deploy Firestore Rules/Indexes
cd /d %~dp0
echo === Firestore ルール/インデックスをデプロイします ===
echo ※ 初回は npx が Firebase CLI を取得します。ログインが必要です。
echo    npx firebase-tools login
pause
npx firebase-tools deploy --only firestore:rules,firestore:indexes || goto :error
echo 完了しました。
pause
goto :eof

:error
echo 失敗しました。Firebase プロジェクト設定やログイン状態を確認してください。
pause

