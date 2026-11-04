# Debian 13 (trixie) ships SQLite >= 3.43, which the FTS5 index requires.
FROM python:3.13-slim-trixie

ENV PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY csvbot ./csvbot
COPY data/sample.csv data/README.md ./data/

# Search index lives in /app/state; put your CSV/DB files in /app/data.
RUN mkdir -p state
ENV DATA_DIR=data DB_PATH=state/index.db
VOLUME ["/app/data", "/app/state"]
CMD ["python", "-m", "csvbot.bot"]
