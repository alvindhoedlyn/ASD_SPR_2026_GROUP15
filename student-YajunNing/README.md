# Flight Recommender (Student 5 - Yajun Ning)

## Release 0 scope

The feature accepts a traveller's route, dates, budget, and ranking preference. It will return
available flight options labelled as best overall, cheapest, fastest, or fewest stops. AI-Mode
will explain recommendations using only flight records supplied by the application.

## Search request contract

The frontend uses these stable field names:

- `origin`
- `destination`
- `departure_date`
- `return_date` (optional)
- `max_budget`
- `preference`: `best_overall`, `cheapest`, `fastest`, or `fewest_stops`

`POST /api/flight-searches` retrieves a ten-flight Release 0 catalogue from the database
microservice and returns up to three ranked results. It supports the Sydney-to-Tokyo demo route
and applies the user's maximum budget and selected priority. It does not call an external live
flight API.

When `ai_mode` is enabled, the backend executes a bounded Plan -> Act -> Observe -> Adapt loop,
then uses the Lab-compatible OpenAI client to call local Ollama. Prompt assets prohibit invented
flights and limit the model to explaining the deterministic ranking. If Ollama is unavailable,
the API returns the normal recommendation. A grounding validator checks mentioned flight numbers,
prices, and stop counts; unsafe model text is replaced with a deterministic explanation and
`ai.status = guarded_fallback`.

## Current local service architecture

The Student 5 feature can now run as three containers using the Compose file in this folder:

- `frontend-service` - Nginx static frontend on port `5505`; proxies `/api/*` to the backend.
- `backend-service` - Flask recommendation API on host port `5605` (container port `5005`).
- `database-service` - Flask database service on host port `5705` (container port `6005`).

Those `55xx/56xx/57xx` ports are only for isolated Student 5 development. In the integrated
group application, users log in through the shared frontend on `http://localhost:3000` and open
the Flight Recommender frontend on `http://localhost:3005` from the JourneyBuddy homepage.
The integrated Flight backend and database use ports `5005` and `6005` respectively.

The homepage passes the shared session token to the Flight frontend once. The Flight frontend
then sends the token to its backend in the `X-Session-Token` header. Before serving saved-flight
CRUD requests, the backend verifies that token with the shared authentication service and derives
the username from the verified session. A caller therefore cannot read or modify another user's
shortlist by supplying a different username.

The root `student-YajunNing/Dockerfile` is temporarily retained so the group's existing shared
Compose history remains understandable, but the group root Compose now builds the dedicated
frontend, backend, and database Dockerfiles. The shared JourneyBuddy homepage links to the
Flight frontend at `http://localhost:3005`.

The database service owns the read-only flight catalogue and the user-owned `saved_flights`
records. Users cannot add, edit, or delete airline catalogue prices. The frontend provides CRUD
for the traveller's shortlist instead:

- Create: save a recommended flight for selected travel dates.
- Read: view only the signed-in user's saved flights.
- Update: change a personal status (`considering`, `booked`, or `cancelled`) and note.
- Delete: remove a flight from the user's shortlist.

The backend exposes these operations through `/api/saved-flights`, while SQLite remains accessible
only through the separate database microservice. The catalogue is seeded with ten flight records
on first start.

Both the shared `client` and `admin` demo accounts can access the Flight Recommender. Neither role
is given a catalogue-price editing screen: flight data is treated as provider-owned, while the
user-owned saved-flight shortlist is the feature's CRUD resource.

## Release 1: local MCP and grounded RAG

Release 1 preserves all Release 0 search, AI-Mode, agentic-loop, login, and saved-flight CRUD
behaviour. It adds two explicit frontend interactions that always pass through the Flight backend:

- **MCP recommendation:** the frontend calls `POST /api/mcp/recommend-flights`; the backend invokes
  the registered `recommend_flights` tool on the shared local MCP server; the tool calls the bounded
  Flight recommendation API and returns a structured result.
- **Grounded RAG question:** the frontend calls `POST /api/rag/answer`; the backend calls the shared
  shared local RAG server at port `5100`; the RAG corpus retrieves approved Flight catalogue context and returns an answer with
  source citations and a confidence category. Unsupported questions return `insufficient_context`.

The approved Flight knowledge is stored in `ai-services/rag-server/knowledge/flights.md`. The shared
RAG server retrieves only local project documents and instructs Ollama not to use outside knowledge
or invent facts. Flight answers are also checked against parsed catalogue constraints (flight number,
price, stops, and budget). If a local-model answer conflicts with those facts, the service replaces it
with a deterministic answer built from the retrieved record. If no relevant context is available, it
returns an insufficient-context result with no citations.

### Execution boundary

The frontend, backend, and database remain containerised. Ollama/AI-Mode, the MCP server, the RAG
server, and the shared agentic loop run locally and are deliberately absent from Docker Compose.
From a backend container, the local services are reached through `host.docker.internal`:

- MCP: `http://host.docker.internal:5200/mcp`
- RAG: `http://host.docker.internal:5100`
- Ollama: `http://host.docker.internal:11434/v1`

### Integrated startup order

Run the following from the repository root, using separate terminals where indicated:

1. Start Ollama locally with `ollama serve` and make sure `qwen2.5:0.5b` is available.
2. Start the containerised application with `docker compose up -d --build`.
3. In `ai-services/mcp-server`, install its requirements and run `python server.py`.
4. In `ai-services/rag-server`, install its requirements and run `python rag_http_server.py`.
5. Open the shared homepage at `http://localhost:3000`, sign in, and open Flight Recommender, or
   open the feature directly at `http://localhost:3005`.

Run `python student-YajunNing/scripts/validate_release1.py` to print a compact MCP/RAG validation
record suitable for terminal evidence. The frontend's **Release 1 intelligence** panel provides
the required UI evidence.

### CI/CD behaviour

`.github/workflows/student-5-ci.yml` runs the Student 5 unit tests, validates the Student 5 Compose
file, and builds all three images. It sets `MCP_ENABLED=false` and `RAG_ENABLED=false`, so CI does
not depend on non-containerised local services while the production integration code remains in
the feature.
