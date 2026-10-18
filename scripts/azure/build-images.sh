#!/usr/bin/env bash
# Step 3. Builds the 18 service images with Docker and pushes them to Azure Container Registry.
# (Some Azure subscriptions block ACR Tasks, so "az acr build" is not used.)
# The code is copied to .cloud-stage/ first and the web addresses in that copy are rewritten
# (localhost:<port> -> the app's Azure address). The repository source is not changed.
# Needs Docker running on this machine (on GitHub Actions it is already available).
set -euo pipefail

RESOURCE_GROUP="${RESOURCE_GROUP:-journeybuddy-rg}"
LOCATION="${LOCATION:-australiaeast}"
PARALLEL="${PARALLEL:-3}"
PYTHON="$(command -v python3 || command -v python)"   # Git Bash on Windows often only has "python"
REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO_ROOT"   # relative paths below avoid Windows path conversion problems

REGISTRY=$(az group show --name "$RESOURCE_GROUP" --query "tags.registryName" -o tsv)
ENV_NAME=$(az group show --name "$RESOURCE_GROUP" --query "tags.envName" -o tsv)
DOMAIN=$(az containerapp env show --name "$ENV_NAME" --resource-group "$RESOURCE_GROUP" \
  --query properties.defaultDomain -o tsv)

if ! az acr show --name "$REGISTRY" --resource-group "$RESOURCE_GROUP" --output none 2>/dev/null; then
  az acr create --name "$REGISTRY" --resource-group "$RESOURCE_GROUP" --location "$LOCATION" \
    --sku Basic --admin-enabled true --output none
  echo "Waiting for the registry address to become available"
  sleep 30
fi

SERVER=$(az acr show --name "$REGISTRY" --query loginServer -o tsv)
REG_PASSWORD=$(az acr credential show --name "$REGISTRY" --query "passwords[0].value" -o tsv)
echo "$REG_PASSWORD" | docker login "$SERVER" --username "$REGISTRY" --password-stdin

STAGE=".cloud-stage"
LOGS=".cloud-build-logs"
rm -rf "$STAGE" "$LOGS"
mkdir -p "$STAGE" "$LOGS"
tar --exclude=./.git --exclude=./.cloud-stage --exclude=./.cloud-build-logs \
  --exclude=node_modules --exclude=__pycache__ -cf - . | tar -C "$STAGE" -xf -

# Rewrite the localhost links and nginx proxy targets in the staged copy.
docker compose -f docker-compose.yml -f docker-compose.cloud.yml config --format json \
  | "$PYTHON" scripts/azure/plan.py rewrite "$STAGE" "$DOMAIN"

build_one() {   # app context dockerfile target
  local app="$1" context="$2" dockerfile="$3" target="$4"
  local extra=()
  [ -n "$target" ] && extra=(--target "$target")
  local image="$SERVER/jb/$app:latest"
  # linux/amd64 is what Azure Container Apps runs, even if this computer is ARM.
  if docker build --platform linux/amd64 --tag "$image" \
        --file "$STAGE/$context/$dockerfile" ${extra[@]+"${extra[@]}"} "$STAGE/$context" \
        > "$LOGS/$app.log" 2>&1 \
     && docker push "$image" >> "$LOGS/$app.log" 2>&1; then
    echo "built and pushed  $app"
  else
    echo "FAILED $app (see $LOGS/$app.log)"
    tail -20 "$LOGS/$app.log"
    return 1
  fi
}

PLAN=$(docker compose -f docker-compose.yml -f docker-compose.cloud.yml config --format json \
  | "$PYTHON" scripts/azure/plan.py plan "$DOMAIN")

pids=()
while IFS='|' read -r app kind port ingress context dockerfile target envs; do
  while [ "$(jobs -rp | wc -l)" -ge "$PARALLEL" ]; do sleep 2; done
  build_one "$app" "$context" "$dockerfile" "$target" &
  pids+=($!)
done < <(echo "$PLAN" | "$PYTHON" scripts/azure/plan.py lines)

status=0
for pid in "${pids[@]}"; do wait "$pid" || status=1; done
rm -rf "$STAGE"
[ "$status" = 0 ] && echo "All images built and pushed to $SERVER" || { echo "Some builds failed" >&2; exit 1; }