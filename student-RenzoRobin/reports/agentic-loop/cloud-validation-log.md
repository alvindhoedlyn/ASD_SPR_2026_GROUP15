# Cloud Deployment Report Review - validation log

Run at: 2026-10-28 21:08:49 AUS Eastern Daylight Time

OBSERVE: .github/workflows/cloud-deployment.yml: present, contains azure/login, workflow_dispatch, needs:.
scripts/azure: 7 deployment script(s): build-images.sh, cleanup.sh, deploy-azure-env.sh, deploy-azure.sh, deployment-testing.sh, env-setup.sh, gh-secrets-setup.sh.
deploy-azure.sh: --ingress present, internal and external ingress both present.
docker-compose.cloud.yml: flags that must be off and are off: none; information (AI runs on the internal Ollama app): AI_MODE_ENABLED=true, MCP_ENABLED=true, RAG_ENABLED=true, MULTI_AGENT_ENABLED=true.
deployment results (reports/cloud/deployment-results.md):
# Cloud deployment results

- Target: Azure Container Apps, resource group `journeybuddy-rg` (australiaeast)
- Shared frontend: https://jb-shared-frontend.proudforest-e5cb0880.australiaeast.azurecontainerapps.io
- Checked: 2026-10-28 09:49:20 UTC
- AI-Mode, MCP, RAG and Multi-Agent: enabled (internal apps)

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

Overall: Success

IMPLEMENTATION: The cloud deployment evidence is in place. The workflow, scripts, and cloud configuration are correctly set up. The deployed application passed its checks. The AI Mode is enabled, and the MCP, RAG, and Multi-Agent are running as internal container apps. The deployment results are successful.
REVIEW: The implementation recommendation is supported by the evidence. However, I flag that the deployment results report a 401 status code for the "Shared backend via shared frontend" check, indicating potential authentication issues.

## Human validation and release decision

- Workflow run: https://github.com/alvindhoedlyn/ASD_SPR_2026_GROUP15/actions/runs/40665944725 (Success, 14 of 14 checks passed)
- Configuration: AI Mode, MCP, RAG and Multi-Agent are enabled as internal container apps. Only the six frontends are public.
- Note on the 401: the shared backend check calls /api/verify-session without a token and is expected to return 401. It confirms the service is reachable and rejecting a missing session.
- Multi-Agent test on the live site: a request ran through Planner, Worker and Reviewer (llama3.1:8b) and was accepted by the human reviewer.
- Release decision: READY
- Approver: Renzo Van Herli Robin
- Date: 2026-10-28
