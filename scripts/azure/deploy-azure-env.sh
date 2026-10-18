#!/usr/bin/env bash
# Step 2. Creates the Container Apps environment. Kept separate because it is slow.
# It must exist before the images are built, because the environment's domain is part of
# every app's web address and those addresses are written into the frontends.
set -euo pipefail

RESOURCE_GROUP="${RESOURCE_GROUP:-journeybuddy-rg}"
LOCATION="${LOCATION:-australiaeast}"

ENV_NAME=$(az group show --name "$RESOURCE_GROUP" --query "tags.envName" -o tsv)
if az containerapp env show --name "$ENV_NAME" --resource-group "$RESOURCE_GROUP" --output none 2>/dev/null; then
  echo "Environment $ENV_NAME already exists"
else
  az containerapp env create --name "$ENV_NAME" --resource-group "$RESOURCE_GROUP" \
    --location "$LOCATION" --logs-destination none --output none
fi

DOMAIN=$(az containerapp env show --name "$ENV_NAME" --resource-group "$RESOURCE_GROUP" \
  --query properties.defaultDomain -o tsv)
echo "Environment domain: $DOMAIN"