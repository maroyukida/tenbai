@echo off
title Pocchari Chat Web (Emulator)
cd /d %~dp0
echo === 依存関係をインストール ===
call npm install || goto :error
echo === エミュレータ接続で Web を起動 ===
set EXPO_PUBLIC_USE_EMULATOR=true
set EXPO_PUBLIC_FIREBASE_API_KEY=demo
set EXPO_PUBLIC_FIREBASE_AUTH_DOMAIN=localhost
set EXPO_PUBLIC_FIREBASE_PROJECT_ID=demo-pocchari
set EXPO_PUBLIC_FIREBASE_STORAGE_BUCKET=demo-pocchari.appspot.com
set EXPO_PUBLIC_FIREBASE_MESSAGING_SENDER_ID=0
set EXPO_PUBLIC_FIREBASE_APP_ID=demo
npx expo start --web
goto :eof

:error
echo エラー: Node.js または npm が見つかりません。https://nodejs.org/ から LTS をインストールしてください。
pause
