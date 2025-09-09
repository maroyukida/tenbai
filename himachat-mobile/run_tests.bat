@echo off
title HimaChat Tests
cd /d %~dp0
echo === 依存関係をインストール ===
call npm install || goto :error
echo === テストを実行 ===
npm test
pause
goto :eof

:error
echo エラー: Node.js または npm が見つかりません。https://nodejs.org/ から LTS をインストールしてください。
pause

