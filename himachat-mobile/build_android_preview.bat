@echo off
title EAS Build - Android (preview)
cd /d %~dp0
echo === Expoにログインしていない場合はログインしてください ===
echo npx expo login
pause
call npm install || goto :error
npx eas build --platform android --profile preview
pause
goto :eof

:error
echo 依存関係のインストールに失敗しました。Node.js を確認してください。
pause

