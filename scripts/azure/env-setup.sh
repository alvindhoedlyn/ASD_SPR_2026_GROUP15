#!/usr/bin/env bash
# Step 1. Registers the Azure resource providers, creates the resource group, and stores the
# generated registry and environment names as tags on it. Safe to run twice.
set -euo pipefail

RESOURCE_GROUP="${RESOURCE_GROUP:-journeybuddy-rg}"
LOCATION="${LOCATION:-australiaeast}"

for provider in Microsoft.App Microsoft.ContainerRegistry Microsoft.OperationalInsights; do
  az provider register --namespace "$provider" --wait --output none
done

az group create --name "$RESOURCE_GROUP" --location "$LOCATION" --output none

REGISTRY=$(az group show --name "$RESOURCE_GROUP" --query "tags.registryName" -o tsv)
if [ -z "$REGISTRY" ]; then
  # Registry names must be globally unique, lowercase letters and digits only.
  az group update --name "$RESOURCE_GROUP" --output none \
    --tags registryName="jbregistry${RANDOM}${RANDOM}" envName="journeybuddy-env"
fi

echo "Resource group $RESOURCE_GROUP ready:"
az group show --name "$RESOURCE_GROUP" --query tags -o json