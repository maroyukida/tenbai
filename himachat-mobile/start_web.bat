@echo off
title HimaChat Web Start
cd /d %~dp0
echo === HimaChat Web モードを起動します ===
echo 1) 依存関係をインストール中...
call npm install || goto :error
echo 2) Webサーバを起動します（ブラウザで開きます）
npx expo start --web
goto :eof

:error
echo エラー: Node.js または npm が見つからないか、インストールに失敗しました。
echo 対処: https://nodejs.org/ から LTS をインストールしてください。
pause

