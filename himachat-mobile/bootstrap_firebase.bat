@echo off
title Bootstrap Firebase for Pocchari Chat
cd /d %~dp0
echo === Firebase 初期設定を自動化（ログイン/プロジェクト選択/SDK構成/ルール反映）===
echo ※ ブラウザが開いたら Google アカウントでログインしてください
call npm install || goto :error
node scripts/bootstrap_firebase.js || goto :error
echo === 完了: app.json を更新し、rules/indexes を反映しました ===
echo 次: preflight.bat -> build_android_preview.bat
pause
goto :eof

:error
echo 失敗しました。エラーメッセージを確認して再実行してください。
pause

