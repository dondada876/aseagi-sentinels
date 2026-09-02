#!/usr/bin/env bash
# PROJ344 — one-shot deploy of the sentinel stack to the .91 droplet (137.184.1.91).
# Verify-before-deploy: authenticates the code on the droplet, then brings up WARDEN
# (which bundles PLUMB + TETHER + DOWSER), then health-checks. Idempotent.
#
#   RUN FROM A MACHINE WITH MESH ACCESS TO .91 (not the cloud sandbox — it can't reach the droplet).
#   bash infra/warden/deploy_91.sh
#
# Overridable:
#   DEPLOY_HOST   (default 137.184.1.91)   DEPLOY_BRANCH (default claude/proj344-sentinels)
#   REPO_DIR      (default /opt/asi360)     PORT_WARDEN   (default 8090)
set -euo pipefail

HOST="${DEPLOY_HOST:-137.184.1.91}"
BRANCH="${DEPLOY_BRANCH:-claude/proj344-sentinels}"
REPO_DIR="${REPO_DIR:-/opt/asi360}"
PORT_WARDEN="${PORT_WARDEN:-8090}"

# Hard guard: .86 is DEPRECATED — never deploy there.
if [ "$HOST" = "104.248.69.86" ]; then
  echo "REFUSING: 104.248.69.86 (.86) is DEPRECATED. Deploy target is 137.184.1.91 (.91)."; exit 2
fi

echo "PROJ344 deploy → root@${HOST}  branch=${BRANCH}  repo=${REPO_DIR}"

ssh "root@${HOST}" REPO_DIR="$REPO_DIR" BRANCH="$BRANCH" PORT_WARDEN="$PORT_WARDEN" 'bash -s' <<'REMOTE'
set -euo pipefail
cd "$REPO_DIR"

echo "[1/4] fetch + checkout ${BRANCH}"
git fetch --prune origin
git checkout "$BRANCH"
git pull --ff-only origin "$BRANCH"

echo "[2/4] verify & authenticate the code (dummy tests must pass before we touch containers)"
cd infra
python3 tether/tests/dummy_reanchor_test.py >/dev/null && echo "  TETHER ok"
python3 dowser/tests/dummy_sentinel_test.py >/dev/null && echo "  DOWSER ok"

echo "[3/4] bring up WARDEN (bundles PLUMB + TETHER + DOWSER)"
docker compose -f warden/compose.yaml up -d --build

echo "[4/4] health check"
for i in 1 2 3 4 5 6; do
  if curl -fsS "http://localhost:${PORT_WARDEN}/health" >/dev/null 2>&1; then
    echo "  WARDEN healthy on :${PORT_WARDEN}"; break
  fi
  [ "$i" = 6 ] && { echo "  WARDEN did not become healthy — check: docker logs proj344-warden"; exit 1; }
  sleep 5
done
echo "  containers:"; docker ps --filter "name=proj344-" --format '    {{.Names}}  {{.Status}}  {{.Ports}}'
REMOTE

echo
echo "DEPLOYED. Board: http://${HOST}:${PORT_WARDEN}"
echo "Rollback: ssh root@${HOST} 'cd ${REPO_DIR}/infra && docker compose -f warden/compose.yaml down'"
echo "LIVE mode: set CORPUS_DSN/DATABASE_URL + TWIN_GLOB + COMM_GLOB in warden/compose.yaml, then re-run."
