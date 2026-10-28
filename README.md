# ASD_SPR_2026_GROUP15

Group Project Members:
- Alvindho Edlyn
- Keyuan Gan
- Renzo Van Herli Robin
- Trong Phuc Dao
- Yajun Ning

# JourneyBuddy

The members of Group 15 have collaborated to create JourneyBuddy, a travel planning app that aims to improve the travelling experience for upcoming tourists. The site lets users compare flights, find attractions that match their style, get accommodation recommendations weighted by their own priorities, plan out their trip on a map, and plan their budget.

Each member has integrated AI into their feature: Qwen 2.5 (0.5b) for feature implementation and Llama 3.1 (8b) for code review. Release 2 adds three shared AI services (MCP, RAG and a Multi-Agent server) and a cloud deployment on Azure Container Apps.

## Table of Contents
- [Architecture Overview](#architecture-overview)
- [Services](#services)
- [Prerequisites](#prerequisites)
- [Setup Instructions](#setup-instructions)
- [Running the Application](#running-the-application)
- [AI Services](#ai-services)
- [Cloud Deployment](#cloud-deployment)
- [CI/CD Pipeline](#cicd-pipeline)
- [Testing](#testing)
- [Project Structure](#project-structure)

## Architecture Overview

The application follows a **microservices architecture**, where:
- A **shared frontend/backend/database** provides core platform functionality (auth, shared data).
- Each **student module** is an independent frontend + backend + database trio focused on a specific feature (flights, attractions, accommodation, map routes, budget).
- Three **shared AI services** (MCP, RAG, Multi-Agent) are called by the module backends.
- **Ollama** provides LLM inference to the modules and AI services that need it.
- Locally, all services communicate over Docker networks defined in `docker-compose.yml`. In the cloud, each service runs as its own Azure Container App.

Each module's frontend depends on its backend, and each backend depends on its own database. This dependency chain is enforced in `docker-compose.yml` and mirrored in each module's CI build order.

## Services

| Service | Description | Port |
|---|---|---|
| `shared-frontend` | Main platform UI | 3000 |
| `shared-backend` | Core platform API (auth) | 5000 |
| `shared-database` | Core platform data store | 6000 |
| `student-AlvindhoEdlyn` (+ `-frontend`, `-database`) | Map Routes | 5001 / 3001 / 6001 |
| `student-KeyuanGan-frontend` / `-backend` / `-database` | Budget | 3002 / 5002 / 6002 |
| `student-RenzoRobin-frontend` / `-backend` / `-database` | Accommodation | 3003 / 5003 / 6003 |
| `student-TrongDao` (+ `-backend`, `-database`) | Attractions | 3004 / 5004 / 6004 |
| `student-YajunNing` (+ `yajunning-backend-service`, `yajunning-database-service`) | Flights | 3005 / 5005 / 6005 |
| `rag-server` | Shared RAG service | 5100 |
| `mcp-server` | Shared MCP tool server | 5200 |
| `multi-agent-server` | Shared Planner / Worker / Reviewer workflow | 5300 |
| Ollama | LLM inference (`qwen2.5:0.5b`, `llama3.1:8b`) | 11434 |

## Prerequisites

Make sure you have the following installed before setting up the project:
- [Docker](https://www.docker.com/get-started) and Docker Compose (v2+)
- Git
- Python 3.12
- [Ollama](https://ollama.com) with `qwen2.5:0.5b` and `llama3.1:8b` pulled (for the AI features)
- For the cloud deployment only: the Azure CLI and the GitHub CLI

## Setup Instructions

1. **Clone the repository**
   ```bash
   git clone https://github.com/alvindhoedlyn/ASD_SPR_2026_GROUP15.git
   cd ASD_SPR_2026_GROUP15
   ```

2. **Review environment variables**
   Each service's environment variables (ports, database paths, API URLs, AI switches) are pre-configured in `docker-compose.yml`.

3. **Build and start all services**
   ```bash
   docker compose up --build
   ```
   This builds every service's image (if not already built) and starts the shared platform, each student module and the AI services.

4. **Verify everything is running**
   ```bash
   docker compose ps
   ```
   All services should show a status of `Up`.

## Running the Application

Once all containers are running, the application is accessible via:

| App | URL |
|---|---|
| Main platform | http://localhost:3000 |
| Flights (YajunNing) | http://localhost:3005 |
| Attractions (TrongDao) | http://localhost:3004 |
| Accommodation (RenzoRobin) | http://localhost:3003 |
| Map Routes (AlvindhoEdlyn) | http://localhost:3001 |
| Budget (KeyuanGan) | http://localhost:3002 |

To stop all services:
```bash
docker compose down
```

To rebuild a single service after making changes:
```bash
docker compose up --build <service-name>
```

## AI Services

| Service | Purpose | Switch (per backend) |
|---|---|---|
| `rag-server` | Answers questions from retrieved context (accommodation, flights, budget, itinerary, location) | `RAG_ENABLED` |
| `mcp-server` | Exposes each module's data as MCP tools | `MCP_ENABLED` |
| `multi-agent-server` | Runs a Planner → Worker → Reviewer workflow and waits for a human decision | `MULTI_AGENT_ENABLED` |

- AI features inside each backend are controlled by `AI_MODE_ENABLED`.
- The Multi-Agent server writes its audit trail to `ai-services/multi-agent-server/data/` (`coordination_audit.jsonl`, `workflow_history.jsonl`).
- Each student also has an **agentic loop** (`student-*/agentic_loop` or `agentic-loop`) that collects evidence, asks a local model to assess it and a second model to review the result, then saves a validation log under `reports/agentic-loop/`.

## Cloud Deployment

The application is deployed to **Azure Container Apps** (one app per compose service, 22 in total).

- Only the six frontends have a public address. Backends, databases, Ollama and the AI services are internal; each frontend's nginx proxies `/api` to its backend.
- AI Mode, MCP, RAG and Multi-Agent are enabled in `docker-compose.cloud.yml`.
- `qwen2.5:0.5b` is pulled when the Ollama app starts. `llama3.1:8b` is a larger model and may need to be pulled separately (`ollama pull llama3.1:8b` inside the Ollama app).

### Deploying from GitHub Actions

The workflow `.github/workflows/cloud-deployment.yml` runs on **manual dispatch** (Actions → Cloud Deployment → Run workflow). It logs in to Azure with OIDC, so the repository needs these secrets: `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`. It runs two jobs:

1. `post_commit_tests`: runs the endpoint tests and validates the cloud compose configuration.
2. `deploy`: prepares the Azure resources, builds and pushes the images, deploys the apps, runs the deployment checks and uploads the results as the `cloud-deployment-evidence` artifact.

### Deploying by hand

Scripts are in `scripts/azure/` and run in this order (Git Bash or WSL):

| Step | Script | What it does |
|---|---|---|
| 1 | `env-setup.sh` | Registers providers, creates the resource group and tags |
| 2 | `deploy-azure-env.sh` | Creates the Container Apps environment |
| 3 | `build-images.sh` | Builds the images locally with Docker and pushes them to the registry |
| 4 | `deploy-azure.sh` | Creates or updates the container apps |
| 5 | `deployment-testing.sh` | Runs the deployment checks and writes `reports/cloud/deployment-results.md` |

`cleanup.sh` deletes the whole resource group. Use it when you are finished, since the deployment costs money while it runs.

## CI/CD Pipeline

**Pre-commit.** Each module runs security and test hooks before a commit: Ruff, detect-secrets, pip-audit and endpoint tests (see each module's `.pre-commit-config.yaml`).

**Post-commit.** Each student module has its own GitHub Actions workflow (`student-1-ci.yml` to `student-5-ci.yml`) that runs on every push or pull request affecting that module's folder. Each pipeline:

1. Checks out the code and sets up the Python environment
2. Installs dependencies and runs a syntax check
3. Runs the automated test suite (`pytest`)
4. If tests pass, builds the module's Docker images (database → backend → frontend), tagged to match the names used in `docker-compose.yml`

`integration-ci.yml` checks the modules together, and `cloud-deployment.yml` (above) deploys to Azure.

This ensures that only tested, working code produces new images that can be run via Docker Compose.

## Testing

Run a module's tests from the repository root, for example for the Accommodation module:
```bash
python -m pytest student-RenzoRobin/tests
```
Test results and agentic-loop validation logs are stored in each module's `reports/` folder. Cloud deployment results are in `reports/cloud/`.

## Project Structure

```
.
├── .github/workflows      CI for each module, integration and cloud deployment
├── ai-services            mcp-server, multi-agent-server, rag-server
├── docs                   Release documentation
├── ollama                 Ollama image used in the cloud
├── reports/cloud          Cloud deployment results and human review
├── scripts/azure          Azure deployment scripts
├── shared                 Shared frontend, backend, database and agentic loop
├── student-AlvindhoEdlyn  Map Routes
├── student-KeyuanGan      Budget
├── student-RenzoRobin     Accommodation
├── student-TrongDao       Attractions
├── student-YajunNing      Flights
├── docker-compose.yml         Local development stack
├── docker-compose.cloud.yml   Cloud overrides (Ollama and AI service addresses)
└── README.md
```

Each student folder follows the same layout: `backend/`, `database/`, `frontend/`, `tests/`, `prompts/`, `agentic_loop/` and `reports/`.