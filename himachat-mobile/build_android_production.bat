@echo off
title EAS Build - Android (production)
cd /d %~dp0
echo === Expoにログイン（初回のみ） ===
echo 既にトークンがある場合は環境変数 EXPO_TOKEN を設定してスキップ可
echo 例) set EXPO_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxx
pause
call npm install || goto :error
npx eas build --platform android --profile production --non-interactive || goto :error
echo === ビルド要求を送信しました。EASダッシュボードで進行を確認できます。 ===
pause
goto :eof

:error
echo 失敗しました。Expoログインやネットワークを確認してください。
pause

