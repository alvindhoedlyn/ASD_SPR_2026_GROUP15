#!/usr/bin/env bash
# Step 4. Creates (or updates) one container app per service: databases, then backends, then
# frontends. AI features stay off because the environment variables come from
# docker-compose.cloud.yml. Backends and frontends are public; databases are internal only.
set -euo pipefail
# Git Bash on Windows rewrites values like /app/data/app.db into C:/Program Files/Git/...
export MSYS_NO_PATHCONV=1
export MSYS2_ARG_CONV_EXCL='*'

RESOURCE_GROUP="${RESOURCE_GROUP:-journeybuddy-rg}"
PYTHON="$(command -v python3 || command -v python)"   # Git Bash on Windows often only has "python"
REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO_ROOT"
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
  create_env=(); update_env=()
  if [ "${#env_args[@]}" -gt 0 ]; then
    create_env=(--env-vars "${env_args[@]}")
    update_env=(--set-env-vars "${env_args[@]}")
  fi
  image="$SERVER/jb/$app:latest"

  # Small apps by default; the model server needs far more memory.
  cpu=0.25; mem=0.5Gi
  if [ "$kind" = "llm" ]; then cpu=4; mem=8Gi; fi
  
  if az containerapp show --name "$app" --resource-group "$RESOURCE_GROUP" --output none 2>/dev/null; then
    echo "updating $app"
    az containerapp update --name "$app" --resource-group "$RESOURCE_GROUP" --image "$image" \
      --cpu "$cpu" --memory "$mem" --revision-suffix "r$(date +%s)" \
      ${update_env[@]+"${update_env[@]}"} --output none
  else
    echo "creating $app ($ingress, port $port)"
    az containerapp create --name "$app" --resource-group "$RESOURCE_GROUP" --environment "$ENV_NAME" \
      --image "$image" --registry-server "$SERVER" --registry-username "$REGISTRY" \
      --registry-password "$REG_PASSWORD" --target-port "$port" --ingress "$ingress" \
      --allow-insecure true --min-replicas 1 --max-replicas 1 --cpu "$cpu" --memory "$mem" \
      ${create_env[@]+"${create_env[@]}"} --output none
  fi
done < <(echo "$PLAN" | "$PYTHON" scripts/azure/plan.py lines)
echo "Deployed. Shared frontend: https://jb-shared-frontend.$DOMAIN"