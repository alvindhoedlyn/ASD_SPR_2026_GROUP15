# Cloud deployment results

- Target: Azure Container Apps, resource group `journeybuddy-rg` (australiaeast)
- Shared frontend: https://jb-shared-frontend.happygrass-4972ad4d.australiaeast.azurecontainerapps.io
- Checked: 2026-10-27 11:15:43 UTC
- AI-Mode: enabled (internal Ollama); MCP, RAG and Multi-Agent: disabled (docker-compose.cloud.yml)

| Check | URL | Result |
|---|---|---|
| Frontend shared | https://jb-shared-frontend.happygrass-4972ad4d.australiaeast.azurecontainerapps.io/ | PASS (200) |
| Frontend alvindhoedlyn | https://jb-alvindhoedlyn-frontend.happygrass-4972ad4d.australiaeast.azurecontainerapps.io/ | PASS (200) |
| Frontend keyuangan | https://jb-keyuangan-frontend.happygrass-4972ad4d.australiaeast.azurecontainerapps.io/ | PASS (200) |
| Frontend renzorobin | https://jb-renzorobin-frontend.happygrass-4972ad4d.australiaeast.azurecontainerapps.io/ | PASS (200) |
| Frontend trongdao | https://jb-trongdao-frontend.happygrass-4972ad4d.australiaeast.azurecontainerapps.io/ | PASS (200) |
| Frontend yajunning | https://jb-yajunning-frontend.happygrass-4972ad4d.australiaeast.azurecontainerapps.io/ | PASS (200) |
| Shared backend via shared frontend | https://jb-shared-frontend.happygrass-4972ad4d.australiaeast.azurecontainerapps.io/api/verify-session | PASS (401) |
| Alvindho backend via its frontend | https://jb-alvindhoedlyn-frontend.happygrass-4972ad4d.australiaeast.azurecontainerapps.io/api/journeys | PASS (200) |
| Keyuan backend via its frontend | https://jb-keyuangan-frontend.happygrass-4972ad4d.australiaeast.azurecontainerapps.io/api/expenses | PASS (200) |
| Trong backend via its frontend | https://jb-trongdao-frontend.happygrass-4972ad4d.australiaeast.azurecontainerapps.io/api/places | PASS (200) |
| Yajun backend via its frontend | https://jb-yajunning-frontend.happygrass-4972ad4d.australiaeast.azurecontainerapps.io/api/release1/status | PASS (200) |
| Renzo backend /health via its frontend | https://jb-renzorobin-frontend.happygrass-4972ad4d.australiaeast.azurecontainerapps.io/health | PASS (200) |
| Renzo backend reaches its database | https://jb-renzorobin-frontend.happygrass-4972ad4d.australiaeast.azurecontainerapps.io/accommodations | PASS (200) |
| Renzo frontend proxies /areas | https://jb-renzorobin-frontend.happygrass-4972ad4d.australiaeast.azurecontainerapps.io/areas | PASS (200) |
| Multi-Agent disabled | https://jb-renzorobin-frontend.happygrass-4972ad4d.australiaeast.azurecontainerapps.io/multi-agent/run | PASS (403) |

Overall: Success
