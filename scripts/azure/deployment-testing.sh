#!/usr/bin/env bash
# Step 5. Checks the deployed apps over the internet and writes reports/cloud/deployment-results.md.
# Exits non-zero if any check does not pass.
set -uo pipefail

RESOURCE_GROUP="${RESOURCE_GROUP:-journeybuddy-rg}"
LOCATION="${LOCATION:-australiaeast}"
REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

ENV_NAME=$(az group show --name "$RESOURCE_GROUP" --query "tags.envName" -o tsv)
DOMAIN=$(az containerapp env show --name "$ENV_NAME" --resource-group "$RESOURCE_GROUP" \
  --query properties.defaultDomain -o tsv)
BASE() { echo "https://$1.$DOMAIN"; }

OUT="$REPO_ROOT/reports/cloud/deployment-results.md"
mkdir -p "$(dirname "$OUT")"
STAMP=$(date -u +"%Y-%m-%d %H:%M:%S UTC")
OVERALL=0
ROWS=""

check_status() {   # name url expected_status [curl args...]
  local name="$1" url="$2" expected="$3"; shift 3
  local code
  code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 30 "$@" "$url" || true)
  if [ "$code" = "$expected" ]; then
    ROWS="$ROWS| $name | $url | PASS ($code) |"$'\n'
  else
    ROWS="$ROWS| $name | $url | FAIL (got $code, expected $expected) |"$'\n'
    OVERALL=1
  fi
}

# Apps can take a minute to answer after the deploy finishes.
for i in $(seq 1 12); do
  curl -s -o /dev/null --max-time 10 "$(BASE jb-shared-frontend)/" && break
  sleep 10
done

for app in shared alvindhoedlyn keyuangan renzorobin trongdao yajunning; do
  check_status "Frontend $app" "$(BASE "jb-$app-frontend")/" 200
done
# Every backend is internal (Lab 11): each one is tested through its own frontend's nginx proxy.
check_reachable() {   # name url  (passes when the backend answered: not 000/404/502/503/504)
  local name="$1" url="$2"; shift 2
  local code
  code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 30 "$@" "$url" || true)
  case "$code" in
    000|404|502|503|504) ROWS="$ROWS| $name | $url | FAIL (got $code) |"$'\n'; OVERALL=1 ;;
    *) ROWS="$ROWS| $name | $url | PASS ($code) |"$'\n' ;;
  esac
}
check_reachable "Shared backend via shared frontend" "$(BASE jb-shared-frontend)/api/verify-session"
check_reachable "Alvindho backend via its frontend" "$(BASE jb-alvindhoedlyn-frontend)/api/journeys"
check_reachable "Keyuan backend via its frontend" "$(BASE jb-keyuangan-frontend)/api/expenses"
check_reachable "Trong backend via its frontend" "$(BASE jb-trongdao-frontend)/api/places"
check_reachable "Yajun backend via its frontend" "$(BASE jb-yajunning-frontend)/api/release1/status"
check_status "Renzo backend /health via its frontend" "$(BASE jb-renzorobin-frontend)/health" 200
# Backend -> database over the environment's internal network, seen through the frontend proxy.
check_status "Renzo backend reaches its database" "$(BASE jb-renzorobin-frontend)/accommodations" 200
check_status "Renzo frontend proxies /areas" "$(BASE jb-renzorobin-frontend)/areas" 200
# AI features must be off in the cloud: this route answers 403 when Multi-Agent is disabled.
check_status "Multi-Agent disabled" "$(BASE jb-renzorobin-frontend)/multi-agent/run" 403 \
  -X POST -H "Content-Type: application/json" -d '{"question":"cloud check"}'

{
  echo "# Cloud deployment results"
  echo
  echo "- Target: Azure Container Apps, resource group \`$RESOURCE_GROUP\` ($LOCATION)"
  echo "- Shared frontend: $(BASE jb-shared-frontend)"
  echo "- Checked: $STAMP"
  echo "- AI-Mode, MCP, RAG and Multi-Agent: disabled (docker-compose.cloud.yml)"
  echo
  echo "| Check | URL | Result |"
  echo "|---|---|---|"
  printf "%s" "$ROWS"
  echo
  if [ "$OVERALL" = 0 ]; then echo "Overall: Success"; else echo "Overall: FAILED"; fi
} > "$OUT"

cat "$OUT"
exit "$OVERALL"