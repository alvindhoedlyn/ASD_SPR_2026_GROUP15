#!/usr/bin/env bash
# One-time, run locally by the owner of the Azure account (needs: az login, gh auth login).
# Creates an Entra app that GitHub Actions can log in as via OIDC (no stored password),
# then stores AZURE_CLIENT_ID, AZURE_TENANT_ID and AZURE_SUBSCRIPTION_ID as repo secrets.
# If you are not an admin of the GitHub repo, the secrets cannot be set automatically:
# the script prints the three values so a repo admin can add them under
# Settings > Secrets and variables > Actions.
set -euo pipefail

GH_REPO="${GH_REPO:-alvindhoedlyn/ASD_SPR_2026_GROUP15}"
GH_BRANCH="${GH_BRANCH:-main}"
APP_NAME="${APP_NAME:-journeybuddy-github-oidc}"

SUBSCRIPTION_ID=$(az account show --query id -o tsv)
TENANT_ID=$(az account show --query tenantId -o tsv)

APP_ID=$(az ad app list --display-name "$APP_NAME" --query "[0].appId" -o tsv)
if [ -z "$APP_ID" ]; then
  APP_ID=$(az ad app create --display-name "$APP_NAME" --query appId -o tsv)
  az ad sp create --id "$APP_ID" --output none
fi

SUBJECT="repo:${GH_REPO}:ref:refs/heads/${GH_BRANCH}"
cat > /tmp/federated.json <<JSON
{"name":"github-${GH_BRANCH}","issuer":"https://token.actions.githubusercontent.com","subject":"${SUBJECT}","audiences":["api://AzureADTokenExchange"]}
JSON
OBJECT_ID=$(az ad app show --id "$APP_ID" --query id -o tsv)
az ad app federated-credential delete --id "$OBJECT_ID" --federated-credential-id "github-${GH_BRANCH}" 2>/dev/null || true
az ad app federated-credential create --id "$OBJECT_ID" --parameters /tmp/federated.json --output none

az role assignment create --assignee "$APP_ID" --role Contributor \
  --scope "/subscriptions/${SUBSCRIPTION_ID}" --output none 2>/dev/null || true

if gh secret set AZURE_CLIENT_ID --repo "$GH_REPO" --body "$APP_ID" \
  && gh secret set AZURE_TENANT_ID --repo "$GH_REPO" --body "$TENANT_ID" \
  && gh secret set AZURE_SUBSCRIPTION_ID --repo "$GH_REPO" --body "$SUBSCRIPTION_ID"; then
  echo "Secrets set on $GH_REPO"
else
  echo "Could not set secrets (not a repo admin?). Give these to a repo admin:"
  echo "AZURE_CLIENT_ID=$APP_ID"
  echo "AZURE_TENANT_ID=$TENANT_ID"
  echo "AZURE_SUBSCRIPTION_ID=$SUBSCRIPTION_ID"
fi
echo "Federated subject: $SUBJECT"