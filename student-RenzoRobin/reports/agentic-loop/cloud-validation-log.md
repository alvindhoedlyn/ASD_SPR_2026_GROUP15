# Cloud Deployment Report Review - validation log

Run at: 2026-10-27 21:37:29 AUS Eastern Daylight Time

OBSERVE FAILED: .github/workflows/cloud-deployment.yml: present, contains azure/login, workflow_dispatch, needs:.
scripts/azure: 7 deployment script(s): build-images.sh, cleanup.sh, deploy-azure-env.sh, deploy-azure.sh, deployment-testing.sh, env-setup.sh, gh-secrets-setup.sh.
docker-compose.cloud.yml: AI flags set to false: MCP_ENABLED, RAG_ENABLED, MULTI_AGENT_ENABLED; STILL ENABLED: AI_MODE_ENABLED.
deployment results (reports/cloud/deployment-results.md):
# Cloud deployment results

- Target: Azure Container Apps, resource group `journeybuddy-rg` (australiaeast)
- Shared frontend: https://jb-shared-frontend.delightfulwater-df0a72cd.australiaeast.azurecontainerapps.io
- Checked: 2026-10-27 07:15:02 UTC
- AI-Mode, MCP, RAG and Multi-Agent: disabled (docker-compose.cloud.yml)

| Check | URL | Result |
|---|---|---|
| Frontend shared | https://jb-shared-frontend.delightfulwater-df0a72cd.australiaeast.azurecontainerapps.io/ | PASS (200) |
| Frontend alvindhoedlyn | https://jb-alvindhoedlyn-frontend.delightfulwater-df0a72cd.australiaeast.azurecontainerapps.io/ | PASS (200) |
| Frontend keyuangan | https://jb-keyuangan-frontend.delightfulwater-df0a72cd.australiaeast.azurecontainerapps.io/ | PASS (200) |
| Frontend renzorobin | https://jb-renzorobin-frontend.delightfulwater-df0a72cd.australiaeast.azurecontainerapps.io/ | PASS (200) |
| Frontend trongdao | https://jb-trongdao-frontend.delightfulwater-df0a72cd.australiaeast.azurecontainerapps.io/ | PASS (200) |
| Frontend yajunning | https://jb-yajunning-frontend.delightfulwater-df0a72cd.australiaeast.azurecontainerapps.io/ | PASS (200) |
| Shared backend via shared frontend | https://jb-shared-frontend.delightfulwater-df0a72cd.australiaeast.azurecontainerapps.io/api/verify-session | PASS (401) |
| Alvindho backend via its frontend | https://jb-alvindhoedlyn-frontend.delightfulwater-df0a72cd.australiaeast.azurecontainerapps.io/api/journeys | PASS (200) |
| Keyuan backend via its frontend | https://jb-keyuangan-frontend.delightfulwater-df0a72cd.australiaeast.azurecontainerapps.io/api/expenses | PASS (200) |
| Trong backend via its frontend | https://jb-trongdao-frontend.delightfulwater-df0a72cd.australiaeast.azurecontainerapps.io/api/places | PASS (200) |
| Yajun backend via its frontend | https://jb-yajunning-frontend.delightfulwater-df0a72cd.australiaeast.azurecontainerapps.io/api/release1/status | PASS (200) |
| Renzo backend /health via its frontend | https://jb-renzorobin-frontend.delightfulwater-df0a72cd.australiaeast.azurecontainerapps.io/health | PASS (200) |
| Renzo backend reaches its database | https://jb-renzorobin-frontend.delightfulwater-df0a72cd.australiaeast.azurecontainerapps.io/accommodations | PASS (200) |
| Renzo frontend proxies /areas | https://jb-renzorobin-frontend.delightfulwater-df0a72cd.australiaeast.azurecontainerapps.io/areas | PASS (200) |
| Multi-Agent disabled | https://jb-renzorobin-frontend.delightfulwater-df0a72cd.australiaeast.azurecontainerapps.io/multi-agent/run | PASS (403) |

Overall: Success
live check: CLOUD_URL not set, so the deployed frontend was not probed.
