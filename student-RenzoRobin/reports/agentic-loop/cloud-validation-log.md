# Cloud Deployment Report Review - validation log

Run at: 2026-10-28 17:18:06 AUS Eastern Daylight Time

OBSERVE: .github/workflows/cloud-deployment.yml: present, contains azure/login, workflow_dispatch, needs:.
scripts/azure: 7 deployment script(s): build-images.sh, cleanup.sh, deploy-azure-env.sh, deploy-azure.sh, deployment-testing.sh, env-setup.sh, gh-secrets-setup.sh.
deploy-azure.sh: --ingress present, internal and external ingress both present.
docker-compose.cloud.yml: flags that must be off and are off: MCP_ENABLED, RAG_ENABLED, MULTI_AGENT_ENABLED; information (AI runs on the internal Ollama app): AI_MODE_ENABLED=true.
deployment results (reports/cloud/deployment-results.md):
# Cloud deployment results

- Target: Azure Container Apps, resource group `journeybuddy-rg` (australiaeast)
- Shared frontend: https://jb-shared-frontend.proudforest-e5cb0880.australiaeast.azurecontainerapps.io
- Checked: 2026-10-28 00:21:39 UTC
- AI-Mode: enabled (internal Ollama); MCP, RAG and Multi-Agent: disabled (docker-compose.cloud.yml)

| Check | URL | Result |
|---|---|---|
| Frontend shared | https://jb-shared-frontend.proudforest-e5cb0880.australiaeast.azurecontainerapps.io/ | PASS (200) |
| Frontend alvindhoedlyn | https://jb-alvindhoedlyn-frontend.proudforest-e5cb0880.australiaeast.azurecontainerapps.io/ | PASS (200) |
| Frontend keyuangan | https://jb-keyuangan-frontend.proudforest-e5cb0880.australiaeast.azurecontainerapps.io/ | PASS (200) |
| Frontend renzorobin | https://jb-renzorobin-frontend.proudforest-e5cb0880.australiaeast.azurecontainerapps.io/ | PASS (200) |
| Frontend trongdao | https://jb-trongdao-frontend.proudforest-e5cb0880.australiaeast.azurecontainerapps.io/ | PASS (200) |
| Frontend yajunning | https://jb-yajunning-frontend.proudforest-e5cb0880.australiaeast.azurecontainerapps.io/ | PASS (200) |
| Shared backend via shared frontend | https://jb-shared-frontend.proudforest-e5cb0880.australiaeast.azurecontainerapps.io/api/verify-session | PASS (401) |
| Alvindho backend via its frontend | https://jb-alvindhoedlyn-frontend.proudforest-e5cb0880.australiaeast.azurecontainerapps.io/api/journeys | PASS (200) |
| Keyuan backend via its frontend | https://jb-keyuangan-frontend.proudforest-e5cb0880.australiaeast.azurecontainerapps.io/api/expenses | PASS (200) |
| Trong backend via its frontend | https://jb-trongdao-frontend.proudforest-e5cb0880.australiaeast.azurecontainerapps.io/api/places | PASS (200) |
| Yajun backend via its frontend | https://jb-yajunning-frontend.proudforest-e5cb0880.australiaeast.azurecontainerapps.io/api/release1/status | PASS (200) |
| Renzo backend /health via its frontend | https://jb-renzorobin-frontend.proudforest-e5cb0880.australiaeast.azurecontainerapps.io/health | PASS (200) |
| Renzo backend reaches its database | https://jb-renzorobin-frontend.proudforest-e5cb0880.australiaeast.azurecontainerapps.io/accommodations | PASS (200) |
| Renzo frontend proxies /areas | https://jb-renzorobin-frontend.proudforest-e5cb0880.australiaeast.azurecontainerapps.io/areas | PASS (200) |
| Multi-Agent disabled | https://jb-renzorobin-frontend.proudforest-e5cb0880.australiaeast.azurecontainerapps.io/multi-agent/run | PASS (403) |

Overall: Success

IMPLEMENTATION: Overall: Success Reason: The frontend shared and backend via shared frontend URLs are present and the AI-Mode is enabled, indicating the deployment is in place and the AI mode is running.
REVIEW: The implementation recommendation appears to be supported by the evidence. However, I would like to flag that the "AI-Mode" is only enabled for the internal Ollama app, and there is no explicit evidence that the AI mode is running for the other frontends.
