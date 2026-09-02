# WARDEN — Evidence-Integrity Orchestrator: runs PLUMB + TETHER + DOWSER + serves the combined board.
# BUILD CONTEXT MUST BE infra/  (so it can COPY the sibling sentinel dirs):
#   docker build -f warden/Dockerfile -t proj344-warden infra/
# or via the compose in this dir (context: ..).
FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir duckdb rapidfuzz psycopg2-binary
# the three sentinels + WARDEN (context = infra/)
COPY plumb  ./plumb
COPY tether ./tether
COPY dowser ./dowser
COPY warden ./warden
ENV PORT=8090
ENV DROPLET_HOST=137.184.1.91
EXPOSE 8090
CMD ["python3", "warden/serve.py"]
