#!/usr/bin/env bash
# Deletes the resource group (registry, environment, all apps): this stops all billing.
# Asks you to type the name to confirm unless CI is set.
set -euo pipefail

RESOURCE_GROUP="${RESOURCE_GROUP:-journeybuddy-rg}"

if [ -z "${CI:-}" ]; then
  read -r -p "Type the resource group name ($RESOURCE_GROUP) to delete it: " answer
  [ "$answer" = "$RESOURCE_GROUP" ] || { echo "Cancelled"; exit 1; }
fi
az group delete --name "$RESOURCE_GROUP" --yes --no-wait
echo "Deletion started. Check with: az group show --name $RESOURCE_GROUP"