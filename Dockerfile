FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY ytanalyzer ./ytanalyzer
COPY exports ./exports
EXPOSE 3500
CMD sh -c "waitress-serve --call --listen=0.0.0.0:${PORT:-3500} ytanalyzer.webapp.app:create_app"
