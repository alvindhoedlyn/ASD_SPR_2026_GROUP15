"""
Raw HTTP server (no MCP protocol) that backend services POST to.

Runs locally, NOT in Docker. Default port 5100 (deliberately different
from any student backend's port — student-RenzoRobin's backend already
uses 5003, so this avoids that collision; adjust PORT if it collides with
anything else on your machine).

Endpoints:
    GET  /health
    POST /refresh     {"caller": "..."}
    POST /retrieve    {"query": "...", "k": 5, "caller": "..."}
    POST /activities  {"location": "Bondi Beach", "weather": "Light Rain", "k": 4, "caller": "..."}
    POST /itinerary/search  {"query": "what can I do at Bondi when it rains?", "caller": "..."}
                      Always returns the top 5 most relevant itinerary results (k@5) plus
                      precision_at_5. Any "k" in the request is ignored.
    POST /answer      {"query": "...", "k": 5, "caller": "..."}

Run:
    cd ai-services/rag-server
    python rag_http_server.py
"""

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from rag_pipeline import (
    answer_question,
    refresh_corpus,
    retrieve_activities,
    retrieve_context,
    search_itinerary,
)


class RAGHandler(BaseHTTPRequestHandler):
    def _send_json(self, status_code: int, payload: dict):
        response = json.dumps(payload).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-RAG-Mode")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Content-Length", str(len(response)))
        self.end_headers()
        self.wfile.write(response)

    def _read_json(self):
        content_length = int(self.headers.get("Content-Length", "0"))
        if content_length == 0:
            return {}
        raw = self.rfile.read(content_length)
        if not raw:
            return {}
        return json.loads(raw.decode("utf-8"))

    def do_OPTIONS(self):
        self._send_json(200, {})

    def do_GET(self):
        if self.path == "/health":
            self._send_json(200, {"status": "ok", "service": "rag-server"})
            return
        self._send_json(404, {"status": "error", "error": "not_found"})

    def do_POST(self):
        try:
            payload = self._read_json()
        except Exception as exc:
            self._send_json(400, {"status": "error", "error": f"invalid_json: {exc}"})
            return

        try:
            if self.path == "/refresh":
                caller = (payload.get("caller") or "student").strip() or "student"
                result = refresh_corpus(caller=caller)
                self._send_json(200 if result.get("status") == "success" else 500, result)
                return

            if self.path == "/retrieve":
                query = (payload.get("query") or "").strip()
                if not query:
                    self._send_json(400, {"status": "error", "error": "query is required"})
                    return
                k = int(payload.get("k", 5))
                caller = (payload.get("caller") or "student").strip() or "student"
                result = retrieve_context(query=query, k=k, caller=caller)
                self._send_json(200 if result.get("status") == "success" else 500, result)
                return

            if self.path == "/itinerary/search":
                query = (payload.get("query") or "").strip()
                if not query:
                    self._send_json(400, {"status": "error", "error": "query is required"})
                    return
                # k is fixed at 5 (k@5) inside search_itinerary; a client-supplied k is ignored.
                caller = (payload.get("caller") or "itinerary").strip() or "itinerary"
                result = search_itinerary(query=query, caller=caller)
                self._send_json(200 if result.get("status") == "success" else 500, result)
                return

            if self.path == "/activities":
                location = (payload.get("location") or "").strip()
                if not location:
                    self._send_json(400, {"status": "error", "error": "location is required"})
                    return
                weather = (payload.get("weather") or "").strip() or None
                k = int(payload.get("k", 4))
                caller = (payload.get("caller") or "itinerary").strip() or "itinerary"
                result = retrieve_activities(location=location, weather=weather, k=k, caller=caller)
                if result.get("status") == "success":
                    status_code = 200
                elif result.get("error") == "unknown_location":
                    status_code = 404
                else:
                    status_code = 500
                self._send_json(status_code, result)
                return

            if self.path == "/answer":
                query = (payload.get("query") or "").strip()
                if not query:
                    self._send_json(400, {"status": "error", "error": "query is required"})
                    return
                k = int(payload.get("k", 5))
                caller = (payload.get("caller") or "student").strip() or "student"
                result = answer_question(query=query, k=k, caller=caller)
                # insufficient_context is a valid, expected outcome — still 200
                status_code = 200 if result.get("status") in ("success", "insufficient_context") else 500
                self._send_json(status_code, result)
                return

            self._send_json(404, {"status": "error", "error": "not_found"})
        except Exception as exc:
            self._send_json(500, {"status": "error", "error": str(exc)})


def main():
    host = "0.0.0.0"
    port = int(os.getenv("PORT", "5100"))
    server = ThreadingHTTPServer((host, port), RAGHandler)
    print(f"RAG HTTP server running on {host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()