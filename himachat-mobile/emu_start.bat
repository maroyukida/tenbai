@echo off
title Firebase Emulators (Auth/Firestore)
cd /d %~dp0
echo === Firebase Emulators を起動します（Auth:9099 / Firestore:8080）===
echo ※ 初回は npx が Firebase CLI を取得します
npx firebase-tools emulators:start --only auth,firestore
pause

