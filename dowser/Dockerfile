# Corroboration Gap Sentinel — agnostic, independent, single-purpose.
FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir rapidfuzz psycopg2-binary
COPY corroborate.py sentinel.py ./
COPY tests ./tests
COPY samples ./samples
# Agnostic inputs (override at run):
ENV FACTS_JSON=/app/samples/gap_facts.sample.json
ENV COMM_GLOB=/app/samples/comm.sample.json
# Prove health with the dummy test, then run one pass.
CMD ["sh", "-c", "python3 tests/dummy_sentinel_test.py && python3 sentinel.py"]
