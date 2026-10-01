# Student 5 Release 1 Evidence Checklist

Feature: **Flight Recommender**  
Student: **Yajun Ning**

## Implemented contribution

- Retained the three Release 0 containers: frontend, backend/API, and database.
- Added frontend access to shared local MCP and RAG services through the Flight backend.
- Registered read-only Flight MCP tools: `recommend_flights` and `flight_details`.
- Added approved Flight catalogue knowledge to the shared local RAG corpus.
- Returned grounded answers with source citations and confidence categories.
- Added post-generation Flight fact validation and a deterministic grounded fallback.
- Added an insufficient-context response for unsupported claims.
- Kept AI-Mode, MCP, RAG, and the shared agentic loop outside Docker Compose.
- Updated Student 5 CI so MCP and RAG are retained but disabled during CI execution.

## Screenshot and evidence list

1. Shared homepage on `http://localhost:3000` and link to Flight Recommender.
2. Flight page on `http://localhost:3005` showing Release 0 search still operational.
3. MCP panel after **Run MCP recommendation**, including structured catalogue results.
4. RAG panel showing a supported answer, `Confidence`, and a `flights.md` source citation.
5. RAG panel showing the safe insufficient-context response for an unsupported question.
6. Terminal output from `python student-YajunNing/scripts/validate_release1.py`.
7. `docker compose ps` showing the Student 5 frontend, backend, and database containers running.
8. Successful `Student YajunNing CI` GitHub Actions run.
9. GitHub commit/PR showing identifiable Student 5 Release 1 changes.
10. Automated test output showing all 18 Flight tests pass, including the RAG hallucination-regression test.

## Recommended demo inputs

MCP form:

- Origin: `Sydney`
- Destination: `Tokyo`
- Departure: any valid future date
- Return: a later date
- Budget: `1000`
- Priority: `Best overall`

RAG supported query:

`Which direct Sydney to Tokyo flight costs less than AUD 700?`

Expected grounded fact: Jetstar JQ11, AUD $620, citation
`flights.md#Direct Sydney to Tokyo flights below AUD 700`.

RAG unsupported query:

`Which flight includes a free helicopter transfer?`

Expected result: `insufficient_context`, no citations, confidence `Insufficient`.

## Individual contribution log template

| Date | Work completed | Evidence/commit |
|---|---|---|
| YYYY-MM-DD | Added Flight MCP tools and backend proxy endpoint | commit/PR link |
| YYYY-MM-DD | Added Flight RAG corpus, citations, confidence, and grounding validation | commit/PR link |
| YYYY-MM-DD | Added Release 1 frontend interaction panel | commit/PR link |
| YYYY-MM-DD | Updated Student 5 CI and completed validation | Actions/commit link |
