Resale Radar — Deploy Guide
===========================

Quick Start (local)
- Install: `pip install -r requirements.txt`
- Run (Windows): `powershell -ExecutionPolicy Bypass -File scripts/serve.ps1 -Port 3500`
- Run (Unix): `bash scripts/serve.sh` (uses `$PORT` or 3500)
- Open: http://localhost:3500/resale

Docker
- Build: `docker build -t resale-radar .`
- Run: `docker run -p 3500:3500 --rm resale-radar`
- Open: http://localhost:3500/resale

Vercel (Serverless)
- Requirements: Vercel account + CLI (`npm i -g vercel`)
- Files added: `api/index.py`, `vercel.json`
- Deploy:
  - First time: `vercel` (follow prompts)
  - Subsequent: `vercel --prod`
- Notes:
  - Serverless filesystem is ephemeral/read-only: CSV 更新は別ホストで生成し、ここでは閲覧専用にする運用がおすすめです。
  - `.env` の値は Vercel Project Settings → Environment Variables で設定。

Render / Fly.io / Railway / Heroku
- Use the provided `Dockerfile` (Render/Fly/Railway) or `Procfile` (Heroku)
- Set env vars as needed; no AliExpress keys required, but adding them improves results:
  - `ALIEXPRESS_APP_KEY`, `ALIEXPRESS_APP_SECRET`, `ALIEXPRESS_TRACKING_ID`
- Ensure the platform forwards `$PORT` to the container (the entrypoint honors `$PORT`).

Data
- The app reads/writes CSVs under `exports/`.
- For stateless deploys, mount a volume or external storage if persistence is required.

Notes
- Respect target sites’ terms. Keep delays conservative when scraping.
- Without AE keys, AliExpress matches are heuristic (web search + HTML parsing).
