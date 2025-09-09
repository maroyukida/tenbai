@echo off
REM Start headless scheduler (watch/export/fetch/refetch/rank/serve)
setlocal
cd /d "%~dp0\.."
set PY=.\.venv\Scripts\python.exe
if not exist "%PY%" set PY=python
"%PY%" -m ytanalyzer.tools.headless_scheduler --serve --channels-file "C:\Users\mouda\yutura_channels.ndjson"
