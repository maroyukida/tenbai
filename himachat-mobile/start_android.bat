@echo off
title HimaChat Android Start
cd /d %~dp0
echo === HimaChat Android モードを起動します ===
echo 1) 依存関係をインストール中...
call npm install || goto :error
echo 2) Expo を起動します（この後、a キーでエミュレータ起動）
npx expo start
echo 3) Android 実機で試す場合は、端末の Expo Go アプリで表示された QR を読み取ってください。
pause
goto :eof

:error
echo エラー: Node.js または npm が見つからないか、インストールに失敗しました。
echo 対処: https://nodejs.org/ から LTS をインストールしてください。
pause

