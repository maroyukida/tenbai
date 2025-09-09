@echo off
title EAS Submit - Google Play (Android)
cd /d %~dp0
echo === Google Play への提出 ===
echo 事前にサービスアカウントJSONを用意してください。
echo 例) C:\path\to\service-account.json
set /p GP_JSON=サービスアカウントJSONのフルパスを入力してください:
if not exist "%GP_JSON%" (
  echo ファイルが見つかりません: %GP_JSON%
  pause
  goto :eof
)
call npm install || goto :error
echo === 最新のビルド成果物を提出します（--latest） ===
npx eas submit -p android --latest --non-interactive --key "%GP_JSON%" || goto :error
echo 提出完了（Play Consoleでご確認ください）
pause
goto :eof

:error
echo 失敗しました。サービスアカウントやアプリID設定を確認してください。
pause

