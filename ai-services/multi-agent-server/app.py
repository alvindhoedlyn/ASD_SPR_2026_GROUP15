"""Shared Multi-Agent Server (non-containerised, runs locally on port 5300).

Endpoints
  GET  /                         health
  POST /workflow                 run Planner -> Worker -> Reviewer, then wait for a human
  GET  /workflow/status          counts by status and the latest workflow
  GET  /workflow/<id>            one workflow record
  POST /workflow/<id>/decision   human review: accept | partial | correct | reject

Any feature backend calls this server and supplies its own evidence, so the
server is shared and has no feature-specific code.
"""
import os

from flask import Flask, jsonify, request

import coordinator

app = Flask(__name__)
app.json.sort_keys = False  # keep planner -> worker -> reviewer order in responses


@app.get("/")
def health():
    return jsonify({
        "service": "multi-agent-server",
        "status": "ok",
        "agents": ["planner", "worker", "reviewer"],
        "human_review": sorted(coordinator.DECISIONS),
    })


@app.post("/workflow")
def run_workflow():
    payload = request.get_json(silent=True) or {}
    try:
        record = coordinator.run_workflow(
            payload.get("user_request"),
            feature=payload.get("feature", "general"),
            evidence=payload.get("evidence"),
            caller=payload.get("caller", "student"),
        )
    except coordinator.WorkflowError as exc:
        return jsonify({"error": str(exc)}), exc.status_code
    return jsonify(record)


@app.get("/workflow/status")
def workflow_status():
    return jsonify(coordinator.status_summary())


@app.get("/workflow/<workflow_id>")
def get_workflow(workflow_id):
    try:
        return jsonify(coordinator.get_workflow(workflow_id))
    except coordinator.WorkflowError as exc:
        return jsonify({"error": str(exc)}), exc.status_code


@app.post("/workflow/<workflow_id>/decision")
def decide(workflow_id):
    payload = request.get_json(silent=True) or {}
    try:
        record = coordinator.record_decision(
            workflow_id,
            payload.get("decision"),
            note=payload.get("note", ""),
            corrected_output=payload.get("corrected_output", ""),
        )
    except coordinator.WorkflowError as exc:
        return jsonify({"error": str(exc)}), exc.status_code
    return jsonify(record)


if __name__ == "__main__":
    # Bound to all interfaces so the Docker backends can reach it through
    # host.docker.internal (a 127.0.0.1-only server is not reachable from a container).
    app.run(  # noqa: S104
        host=os.environ.get("MULTI_AGENT_HOST", "0.0.0.0"),  # noqa: S104
        port=int(os.environ.get("MULTI_AGENT_PORT", "5300")),
    )