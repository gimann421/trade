# Always-on NEXUS runtime (Stage 0: no live trading, no broker write except the paper-only adapter).
FROM python:3.13-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir PyYAML==6.0.3
COPY nexus ./nexus
ENV PYTHONUNBUFFERED=1
# data/ (SQLite, snapshots) is a mounted volume; secrets arrive only as environment variables.
CMD ["python", "-m", "nexus", "run"]
