# Statement Re-Anchoring & Authentication engine — agnostic, independent, single-purpose.
FROM python:3.12-slim
WORKDIR /app
# duckdb reads the twin parquets; rapidfuzz sharpens matching (optional — difflib is the fallback);
# psycopg2 only used in LIVE mode.
RUN pip install --no-cache-dir duckdb rapidfuzz psycopg2-binary
COPY grid.py matcher.py reanchor.py ./
COPY tests ./tests
# Agnostic inputs (override at run): where the statements + already-scanned twins come from.
ENV TWIN_GLOB=/data/twins/**/*.items.parquet
# STATEMENTS_JSON=/data/statements.json  or  CORPUS_DSN=postgres://...
# Prove health with the dummy test, then run one pass. (Compose can switch CMD to a loop/queue.)
CMD ["sh", "-c", "python3 tests/dummy_reanchor_test.py && python3 reanchor.py"]
