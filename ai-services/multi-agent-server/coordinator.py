"""Coordinates Planner -> Worker -> Reviewer -> Human Review.

Every workflow is saved to two append-only JSONL files:
  - workflow_history.jsonl     full record (a new snapshot is appended when a human decides)
  - coordination_audit.jsonl   one line per event (created, each agent step, decision)
"""
import json
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

import evidence as ev
from agents import planner_agent, reviewer_agent, worker_agent

HISTORY_FILE = "workflow_history.jsonl"
AUDIT_FILE = "coordination_audit.jsonl"
MAX_REQUEST_CHARS = 1000

# decision sent by the human -> workflow status
DECISIONS = {
    "accept": "accepted",
    "partial": "partially_accepted",
    "correct": "corrected",
    "reject": "rejected",
}

_LOCK = threading.RLock()


class WorkflowError(Exception):
    def __init__(self, message, status_code=400):
        super().__init__(message)
        self.status_code = status_code


def _now():
    return datetime.now(timezone.utc).isoformat()


def data_dir():
    path = Path(os.environ.get("MULTI_AGENT_DATA_DIR") or Path(__file__).resolve().parent / "data")
    path.mkdir(parents=True, exist_ok=True)
    return path


def _append(filename, record):
    with _LOCK, open(data_dir() / filename, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def _read_all(filename):
    path = data_dir() / filename
    if not path.exists():
        return []
    records = []
    with _LOCK, open(path, encoding="utf-8") as handle:
        for line in handle:
            try:
                records.append(json.loads(line))
            except ValueError:
                continue  # ignore a damaged line rather than fail every request
    return records


def _audit(workflow_id, event, **details):
    _append(AUDIT_FILE, {"ts": _now(), "workflow_id": workflow_id, "event": event, **details})


def _audit_step(workflow_id, step):
    _audit(
        workflow_id,
        "agent_step_completed",
        agent=step["agent"],
        status=step["status"],
        model=step["model"],
        elapsed_ms=step["elapsed_ms"],
    )


def run_workflow(user_request, feature="general", evidence=None, caller="student"):
    user_request = (user_request or "").strip()
    if not user_request:
        raise WorkflowError("user_request is required")
    if len(user_request) > MAX_REQUEST_CHARS:
        raise WorkflowError(f"user_request must be at most {MAX_REQUEST_CHARS} characters")
    feature = (str(feature or "general").strip() or "general")[:40]
    caller = (str(caller or "student").strip() or "student")[:40]

    items = ev.normalize(evidence)
    workflow_id = uuid.uuid4().hex[:12]
    created_at = _now()
    _audit(workflow_id, "workflow_created", feature=feature, caller=caller, evidence_count=len(items))

    plan = planner_agent.run(user_request, feature, len(items))
    _audit_step(workflow_id, plan)
    work = worker_agent.run(user_request, plan["output"], items)
    _audit_step(workflow_id, work)
    review = reviewer_agent.run(user_request, plan["output"], work, items)
    _audit_step(workflow_id, review)

    record = {
        "workflow_id": workflow_id,
        "created_at": created_at,
        "feature": feature,
        "caller": caller,
        "user_request": user_request,
        "evidence_count": len(items),
        "evidence": items[: ev.MAX_ITEMS],
        "steps": {"planner": plan, "worker": work, "reviewer": review},
        "degraded": any(step["status"] == "fallback" for step in (plan, work, review)),
        "status": "pending_human_review",
        "human_decision": {"status": "pending"},
    }
    _append(HISTORY_FILE, record)
    _audit(workflow_id, "awaiting_human_review", degraded=record["degraded"])
    return record


def get_workflow(workflow_id):
    for record in reversed(_read_all(HISTORY_FILE)):
        if record.get("workflow_id") == workflow_id:
            return record
    raise WorkflowError("workflow not found", 404)


def record_decision(workflow_id, decision, note="", corrected_output=""):
    if decision not in DECISIONS:
        raise WorkflowError("decision must be one of: " + ", ".join(DECISIONS))
    with _LOCK:
        record = get_workflow(workflow_id)
        if record["human_decision"]["status"] != "pending":
            raise WorkflowError("this workflow already has a human decision", 409)
        corrected_output = (corrected_output or "").strip()
        if decision == "correct" and not corrected_output:
            raise WorkflowError("corrected_output is required when the decision is 'correct'")
        record["human_decision"] = {
            "status": DECISIONS[decision],
            "decision": decision,
            "note": (note or "").strip()[:500],
            "corrected_output": corrected_output[:2000] if decision == "correct" else "",
            "decided_at": _now(),
        }
        record["status"] = DECISIONS[decision]
        _append(HISTORY_FILE, record)
        _audit(workflow_id, "human_decision", decision=decision, status=DECISIONS[decision])
    return record


def status_summary():
    latest_by_id = {}
    for record in _read_all(HISTORY_FILE):
        latest_by_id[record["workflow_id"]] = record  # later snapshot replaces earlier
    by_status = {}
    for record in latest_by_id.values():
        by_status[record["status"]] = by_status.get(record["status"], 0) + 1
    latest = list(latest_by_id.values())[-1] if latest_by_id else None
    return {"total": len(latest_by_id), "by_status": by_status, "latest": latest}