# Citation-Integrity / Link-Verify engine — independent, single-purpose container.
# Read-only against the corpus; emits findings + dashboard_data.json; serves the monitor.
FROM python:3.12-slim

WORKDIR /app
RUN pip install --no-cache-dir psycopg2-binary
COPY link_verify.py .
COPY dashboard.html .
COPY samples ./samples
COPY serve.py .

# LIVE mode when DATABASE_URL is set (points at the pg-duckdb lake); OFFLINE otherwise.
ENV PORT=8091
EXPOSE 8091

# Run one pass on start, then serve the dashboard (which re-runs on demand).
CMD ["python3", "serve.py"]
