#!/usr/bin/env bash
# Step 4. Creates (or updates) one container app per service: databases, then backends, then
# frontends. AI features stay off because the environment variables come from
# docker-compose.cloud.yml. Backends and frontends are public; databases are internal only.
set -euo pipefail

RESOURCE_GROUP="${RESOURCE_GROUP:-journeybuddy-rg}"
PYTHON="$(command -v python3 || command -v python)"   # Git Bash on Windows often only has "python"
REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

REGISTRY=$(az group show --name "$RESOURCE_GROUP" --query "tags.registryName" -o tsv)
ENV_NAME=$(az group show --name "$RESOURCE_GROUP" --query "tags.envName" -o tsv)
DOMAIN=$(az containerapp env show --name "$ENV_NAME" --resource-group "$RESOURCE_GROUP" \
  --query properties.defaultDomain -o tsv)
SERVER=$(az acr show --name "$REGISTRY" --query loginServer -o tsv)
REG_PASSWORD=$(az acr credential show --name "$REGISTRY" --query "passwords[0].value" -o tsv)

PLAN=$(cd "$REPO_ROOT" && docker compose -f docker-compose.yml -f docker-compose.cloud.yml config --format json \
  | "$PYTHON" scripts/azure/plan.py plan "$DOMAIN")

while IFS='|' read -r app kind port ingress context dockerfile target envs; do
  envs="${envs%$'\r'}"   # safety: drop a Windows carriage return, if any
  IFS=$'\x1f' read -r -a env_args <<< "$envs"
  env_flag=()
  [ "${#env_args[@]}" -gt 0 ] && env_flag=(--env-vars "${env_args[@]}")
  image="$SERVER/jb/$app:latest"

  if az containerapp show --name "$app" --resource-group "$RESOURCE_GROUP" --output none 2>/dev/null; then
    echo "updating $app"
    az containerapp update --name "$app" --resource-group "$RESOURCE_GROUP" --image "$image" \
      ${env_flag[@]+"${env_flag[@]}"} --output none
  else
    echo "creating $app ($ingress, port $port)"
    # --allow-insecure: services call each other over plain http inside the environment.
    # min-replicas 1: SQLite data lives in the container, so it must not scale to zero.
    az containerapp create --name "$app" --resource-group "$RESOURCE_GROUP" --environment "$ENV_NAME" \
      --image "$image" --registry-server "$SERVER" --registry-username "$REGISTRY" \
      --registry-password "$REG_PASSWORD" --target-port "$port" --ingress "$ingress" \
      --allow-insecure true --min-replicas 1 --max-replicas 1 --cpu 0.25 --memory 0.5Gi \
      ${env_flag[@]+"${env_flag[@]}"} --output none
  fi
done < <(echo "$PLAN" | "$PYTHON" "$REPO_ROOT/scripts/azure/plan.py" lines)

echo "Deployed. Shared frontend: https://jb-shared-frontend.$DOMAIN"