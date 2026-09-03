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
- `backend-service` - Flask recommendation API on port `5605`.
- `database-service` - Flask database service shell on port `5705`.

Those `55xx/56xx/57xx` ports are only for isolated Student 5 development. In the integrated
group application, users log in through the shared service on `http://localhost:8080` and open
the Flight Recommender on `http://localhost:5005` from the JourneyBuddy homepage.

The homepage passes the shared session token to the Flight frontend once. The Flight frontend
then sends the token to its backend in the `X-Session-Token` header. Before serving saved-flight
CRUD requests, the backend verifies that token with the shared authentication service and derives
the username from the verified session. A caller therefore cannot read or modify another user's
shortlist by supplying a different username.

The root `student-YajunNing/Dockerfile` is temporarily retained so the group's existing shared
Compose history remains understandable, but the group root Compose now builds the dedicated
frontend, backend, and database Dockerfiles. The shared JourneyBuddy homepage links to the
Flight frontend at `http://localhost:5005`.

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
