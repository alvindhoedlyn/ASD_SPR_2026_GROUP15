# Cloud deployment results

- Target: Azure Container Apps, resource group `journeybuddy-rg` (australiaeast)
- Shared frontend: https://jb-shared-frontend.gentleglacier-6941a2ce.australiaeast.azurecontainerapps.io
- Checked: 2026-10-22 14:56:24 UTC
- AI-Mode, MCP, RAG and Multi-Agent: disabled (docker-compose.cloud.yml)

| Check | URL | Result |
|---|---|---|
| Frontend shared | https://jb-shared-frontend.gentleglacier-6941a2ce.australiaeast.azurecontainerapps.io/ | PASS (200) |
| Frontend alvindhoedlyn | https://jb-alvindhoedlyn-frontend.gentleglacier-6941a2ce.australiaeast.azurecontainerapps.io/ | PASS (200) |
| Frontend keyuangan | https://jb-keyuangan-frontend.gentleglacier-6941a2ce.australiaeast.azurecontainerapps.io/ | PASS (200) |
| Frontend renzorobin | https://jb-renzorobin-frontend.gentleglacier-6941a2ce.australiaeast.azurecontainerapps.io/ | PASS (200) |
| Frontend trongdao | https://jb-trongdao-frontend.gentleglacier-6941a2ce.australiaeast.azurecontainerapps.io/ | PASS (200) |
| Frontend yajunning | https://jb-yajunning-frontend.gentleglacier-6941a2ce.australiaeast.azurecontainerapps.io/ | PASS (200) |
| Backend shared /health | https://jb-shared-backend.gentleglacier-6941a2ce.australiaeast.azurecontainerapps.io/health | PASS (200) |
| Backend alvindhoedlyn /health | https://jb-alvindhoedlyn-backend.gentleglacier-6941a2ce.australiaeast.azurecontainerapps.io/health | PASS (200) |
| Backend keyuangan /health | https://jb-keyuangan-backend.gentleglacier-6941a2ce.australiaeast.azurecontainerapps.io/health | PASS (200) |
| Backend renzorobin /health | https://jb-renzorobin-backend.gentleglacier-6941a2ce.australiaeast.azurecontainerapps.io/health | PASS (200) |
| Backend trongdao /health | https://jb-trongdao-backend.gentleglacier-6941a2ce.australiaeast.azurecontainerapps.io/health | PASS (200) |
| Backend yajunning /health | https://jb-yajunning-backend.gentleglacier-6941a2ce.australiaeast.azurecontainerapps.io/health | PASS (200) |
| Renzo backend reaches its database | https://jb-renzorobin-backend.gentleglacier-6941a2ce.australiaeast.azurecontainerapps.io/accommodations | PASS (200) |
| Renzo frontend proxies to its backend | https://jb-renzorobin-frontend.gentleglacier-6941a2ce.australiaeast.azurecontainerapps.io/accommodations | PASS (200) |
| Multi-Agent disabled | https://jb-renzorobin-backend.gentleglacier-6941a2ce.australiaeast.azurecontainerapps.io/multi-agent/run | PASS (403) |

Overall: Success
