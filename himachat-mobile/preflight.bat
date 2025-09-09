@echo off
title Preflight Checks
cd /d %~dp0
echo === Running preflight checks ===
set EXPO_PUBLIC_USE_EMULATOR=true
call npm install || goto :error
npm run preflight
pause
goto :eof

:error
echo Node.js/npm が必要です。https://nodejs.org/ からLTSをインストールしてください。
pause
