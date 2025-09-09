@echo off
title Generate Placeholder Assets
cd /d %~dp0
echo === Generating icon.png and splash.png ===
call npm install || goto :error
npm run assets:gen
pause
goto :eof

:error
echo Node.js/npm が必要です。https://nodejs.org/ からLTSをインストールしてください。
pause

