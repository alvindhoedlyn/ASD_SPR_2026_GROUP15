# ASD_SPR_2026_GROUP15

Group Project Members:
- Alvindho Edlyn
- Keyuan Gan
- Renzo Van Herli Robin
- Trong Phuc Dao
- Yajun Ning 

# JourneyBuddy

The members of Group 15 have collaborated to create JourneyBuddy, a travel planning app that aims to improve the travelling experience for upcoming tourists. This site allows users to select a flight, explore through a list of locations, plan out their itinerary, map out their accommodation options and calculate their expected budget. Each member has also managed to integrate AI into our respective features for the sake of feature implementation, performed by Qwen 2.5:0.5b and code review, performed by llama.  

## Table of Contents
- [Architecture Overview](#architecture-overview)
- [Services](#services)
- [Prerequisites](#prerequisites)
- [Setup Instructions](#setup-instructions)
- [Running the Application](#running-the-application)
- [CI/CD Pipeline](#cicd-pipeline)
- [Project Structure](#project-structure)

## Architecture Overview

The application follows a **microservices architecture**, where:
- A **shared frontend/backend/database** provides core platform functionality (auth, shared data).
- Each **student module** is an independent frontend + backend + database trio focused on a specific feature (e.g. accommodation recommendations, flight search, itinerary planning).
- All services communicate over a shared Docker network (`journeybuddy-net`), with an `ai-mode` service (Ollama) providing local LLM inference to modules that need it.

Each module's frontend depends on its backend, and each backend depends on its own database (and, where relevant, on `ai-mode`) — this dependency chain is enforced both in `docker-compose.yml` and mirrored in each module's CI build order.

## Services

| Service | Description | Port |
|---|---|---|
| `shared-frontend` | Main platform UI | 3000 |
| `shared-backend` | Core platform API | 5000 |
| `shared-database` | Core platform data store | 6000 |
| `student-AlvindhoEdlyn` (+ frontend/database) | Student module | 5001 / 3001 / 6001 |
| `student-KeyuanGan-frontend` / `-backend` / `-database` | Student module | 3002 / 5002 / 5702 |
| `student-RenzoRobin-frontend` / `-backend` / `-database` | Accommodation Recommender module | 3003 / 5003 / 6003 |
| `student-TrongDao` (+ backend/database) | Location recommender module | 5004 / 5104 / 5404 |
| `student-YajunNing` (+ backend/database) | Flights module | 3005 / 5005 / 6005 |
| `ai-mode` | Local LLM inference (Ollama) | 11434 |

## Prerequisites

Make sure you have the following installed before setting up the project:
- [Docker](https://www.docker.com/get-started) and Docker Compose (v2+)
- Git
- Python 3.12

## Setup Instructions

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd journeybuddy
   ```

2. **Review environment variables**
   Each service's environment variables (ports, database paths, API URLs) are pre-configured in `docker-compose.yml`.

3. **Build and start all services**
   ```bash
   docker-compose up --build
   ```
   This builds every service's image (if not already built) and starts all containers, including the shared platform, each student module, and the `ai-mode` LLM service.

4. **Verify everything is running**
   ```bash
   docker-compose ps
   ```
   All services should show a status of `Up`.

## Running the Application

Once all containers are running, the application is accessible via:

| App | URL |
|---|---|
| Main platform | http://localhost:3000 |
| Flight Recommender (YajunNing) | http://localhost:3005 |
| Attractions Recommender (TrongDao) | http://localhost:5004 |
| Accommodation Recommender (RenzoRobin) | http://localhost:3003 |
| Itinerary Planner (RenzoRobin) | http://localhost:3001 |
| Itinerary Planner (RenzoRobin) | http://localhost:3002 |


To stop all services:
```bash
docker-compose down
```

To rebuild a single service after making changes:
```bash
docker-compose up --build <service-name>
```

## CI/CD Pipeline

Each student module has its own GitHub Actions workflow that runs automatically on every push or pull request affecting that module's folder. Each pipeline:

1. Checks out the code and sets up the Python environment
2. Installs dependencies and runs a syntax check
3. Runs the automated test suite (`pytest`)
4. If tests pass, builds the module's Docker images (database → backend → frontend), tagged to match the names used in `docker-compose.yml`

This ensures that only tested, working code produces new images that can be run via Docker Compose.

## Project Structure

```
C:.
│   .gitignore
│   docker-compose.yml
│   README.md
│
├───.github
│   └───workflows
│           cloud-deployment.yml
│           integration-ci.yml
│           student-1-ci.yml
│           student-2-ci.yml
│           student-3-ci.yml
│           student-4-ci.yml
│           student-5-ci.yml
│
├───ai-services
│   ├───ai-mode
│   ├───mcp-server
│   ├───multi-agent-server
│   └───rag-server
│
├───docs
│   ├───architecture
│   ├───release-0
│   ├───release-1
│   ├───release-2
│   └───reports
│
├───scripts
│   ├───build
│   ├───deploy
│   └───test
│
├───shared
│   ├───agentic_loop
│   │   ├───config
│   │   │       review_config.py
│   │   │
│   │   ├───core
│   │   │       ai_runner.py
│   │   │       orchestrator.py
│   │   │       prompt_registry.py
│   │   │       reporter.py
│   │   │
│   │   └───pipelines
│   │           review_pipeline.py
│   │
│   ├───backend
│   │       app.py
│   │       Dockerfile
│   │       requirements.txt
│   │
│   ├───configuration
│   │
│   ├───database
│   │       app.py
│   │       Dockerfile
│   │       requirements.txt
│   │       schema.sql
│   │
│   └───frontend
│       │   Dockerfile
│       │   index.html
│       │   login.html
│       │
│       ├───assets
│       ├───css
│       │       style.css
│       │
│       └───js
│               main.js
│
├───student-AlvindhoEdlyn
│   │   Dockerfile
│   │   requirements.txt
│   │
│   ├───backend
│   │       app.py
│   │
│   ├───database
│   │       Dockerfile
│   │       init_db.py
│   │       schema.sql
│   │
│   ├───frontend
│   │   │   Dockerfile
│   │   │   index.html
│   │   │   nginx.conf
│   │   │   script.js
│   │   │
│   │   └───css
│   │           style.css
│   │
│   ├───prompts
│   │       create_day.txt
│   │       create_itinerary.txt
│   │       fill_trip.txt
│   │       itinerary_adjustment.txt
│   │       plan_suggestions.txt
│   │
│   └───tests
│           test_placeholder.py
│
├───student-KeyuanGan
│   │   Dockerfile
│   │
│   ├───backend
│   │       agentic_loop.py
│   │       app.py
│   │       database_client.py
│   │       llm_client.py
│   │       requirements.txt
│   │
│   ├───database
│   │       app.py
│   │       Dockerfile
│   │       requirements.txt
│   │       schema.sql
│   │
│   ├───frontend
│   │       Dockerfile
│   │       index.html
│   │       nginx.conf
│   │
│   └───tests
│           test_placeholder.py
│
├───student-RenzoRobin
│   ├───agentic_loop
│   │   │   main.py
│   │   │
│   │   ├───collectors
│   │   │       db_collector.py
│   │   │       devops_collector.py
│   │   │       endpoints_collector.py
│   │   │
│   │   ├───config
│   │   │       review_config.py
│   │   │
│   │   └───pipelines
│   │           architecture_pipeline.py
│   │           db_pipeline.py
│   │           endpoints_pipeline.py
│   │
│   ├───backend
│   │       app.py
│   │       Dockerfile
│   │       requirements.txt
│   │
│   ├───database
│   │       app.py
│   │       Dockerfile
│   │       requirements.txt
│   │       schema.sql
│   │
│   ├───frontend
│   │   │   Dockerfile
│   │   │   index.html
│   │   │
│   │   ├───css
│   │   │       accommodation.css
│   │   │
│   │   └───js
│   │           accommodation.js
│   │
│   ├───prompts
│   │   ├───devops
│   │   │   ├───implementation
│   │   │   │       system_prompt.txt
│   │   │   │       task_prompt.txt
│   │   │   │
│   │   │   └───review
│   │   │           review_prompt.txt
│   │   │
│   │   └───service
│   │       ├───implementation
│   │       │       context_prompt.txt
│   │       │       system_prompt.txt
│   │       │       task_prompt.txt
│   │       │
│   │       └───review
│   │               review_prompt.txt
│   │
│   └───tests
│           test_backend.py
│           test_database.py
│
├───student-TrongDao
│   │   .dockerignore
│   │   Dockerfile
│   │
│   ├───backend
│   │       app.py
│   │       requirements.txt
│   │
│   ├───database
│   │       app.py
│   │       init_db.py
│   │       requirements.txt
│   │       schema.sql
│   │
│   ├───frontend
│   │   │   health
│   │   │   index.html
│   │   │
│   │   ├───css
│   │   │       location.css
│   │   │
│   │   └───js
│   │           location.js
│   │
│   └───tests
│           test_backend.py
│           test_database.py
│
└───student-YajunNing
    │   docker-compose.yml
    │   Dockerfile
    │   README.md
    │
    ├───backend
    │   │   agentic_loop.py
    │   │   app.py
    │   │   database_client.py
    │   │   Dockerfile
    │   │   flights.py
    │   │   llm_client.py
    │   │   prompt_loader.py
    │   │   requirements.txt
    │   │
    │   └───prompts
    │           flight_recommendation_system.txt
    │           flight_recommendation_task.txt
    │
    ├───database
    │       app.py
    │       Dockerfile
    │       init_db.py
    │       requirements.txt
    │       schema.sql
    │
    ├───frontend
    │       Dockerfile
    │       flight-hero-sunset.png
    │       index.html
    │       nginx.conf
    │       style.css
    │
    └───tests
            test_flight_search.py
            test_placeholder.py
            test_saved_flights.py
```
