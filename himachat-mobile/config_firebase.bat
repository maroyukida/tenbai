@echo off
title Apply Firebase Config to app.json
cd /d %~dp0
echo === Firebase構成値を app.json に書き込みます ===
call npm install || goto :error
npm run config:firebase
pause
goto :eof

:error
echo Node.js/npm が必要です。https://nodejs.org/ からLTSをインストールしてください。
pause

