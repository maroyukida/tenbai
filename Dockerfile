FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY ytanalyzer ./ytanalyzer
COPY exports ./exports

# Expose default port (overridable by $PORT)
EXPOSE 3500

# Use shell to expand $PORT provided by the platform (Render sets PORT).
CMD ["sh", "-c", "waitress-serve --listen=0.0.0.0:${PORT:-3500} ytanalyzer.webapp.app:create_app"]


