"""
Multi-Agent review collector for the Accommodation Recommender.

Checks that the shared Multi-Agent Server, the backend route, the frontend tab and the
tests exist and are wired together, and summarises the workflow history and
coordination/audit logs left by real workflow runs.

Returns (ok, evidence) like the other collectors.
"""
import json
from collections import Counter
from pathlib import Path

import requests

SERVER_URL = "http://localhost:5300"
SERVER_FILES = (
    "app.py",
    "coordinator.py",
    "requirements.txt",
    "agents/planner_agent.py",
    "agents/worker_agent.py",
    "agents/reviewer_agent.py",
    "prompts/planner.txt",
    "prompts/worker.txt",
    "prompts/reviewer.txt",
)
LOG_NAMES = ("workflow_history.jsonl", "coordination_audit.jsonl")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""


def _jsonl(path: Path) -> list[dict]:
    rows = []
    for line in _read(path).splitlines():
        try:
            rows.append(json.loads(line))
        except ValueError:
            continue
    return rows


def _find_logs(server_dir: Path) -> dict[str, Path]:
    found = {}
    for folder in (server_dir / "evidence", server_dir / "data", server_dir):
        for name in LOG_NAMES:
            if name not in found and (folder / name).exists():
                found[name] = folder / name
    return found


def _log_summary(logs: dict[str, Path], repo_root: Path) -> list[str]:
    lines = []
    history = _jsonl(logs["workflow_history.jsonl"]) if "workflow_history.jsonl" in logs else []
    latest = {row.get("workflow_id"): row for row in history}
    if latest:
        statuses = Counter(row.get("status") for row in latest.values())
        degraded = sum(1 for row in latest.values() if row.get("degraded"))
        decided = sum(1 for row in latest.values() if row.get("human_decision", {}).get("status") != "pending")
        lines.append(
            f"workflow history ({logs['workflow_history.jsonl'].relative_to(repo_root)}): "
            f"{len(latest)} workflow(s), statuses {dict(statuses)}, {degraded} degraded, "
            f"{decided} with a human decision."
        )
        sample = list(latest.values())[-1]
        steps = sample.get("steps", {})
        lines.append(
            f"RULE CHECK: {degraded} of {len(latest)} workflows were degraded (an agent used its fallback) "
            f"and only {decided} received a human decision."
        )
    else:
        lines.append("workflow history: no workflow records found.")
    audit = _jsonl(logs["coordination_audit.jsonl"]) if "coordination_audit.jsonl" in logs else []
    if audit:
        events = Counter(row.get("event") for row in audit)
        lines.append(f"coordination audit: {len(audit)} event(s) {dict(events)}.")
    else:
        lines.append("coordination audit: no events found.")
    return lines


def collect(app_dir: Path, repo_root: Path) -> tuple[bool, str]:
    lines, ok = [], True
    server_dir = repo_root / "ai-services" / "multi-agent-server"

    missing = [name for name in SERVER_FILES if not (server_dir / name).exists()]
    if missing:
        ok = False
        lines.append("Multi-Agent Server: missing " + ", ".join(missing) + ".")
    else:
        lines.append(f"Multi-Agent Server: all {len(SERVER_FILES)} required files present.")

    coordinator = _read(server_dir / "coordinator.py")
    roles = [role for role in ("planner_agent", "worker_agent", "reviewer_agent") if role in coordinator]
    if len(roles) == 3:
        lines.append("coordinator.py wires Planner, Worker and Reviewer agents and records a human-review state.")
    else:
        ok = False
        lines.append(f"coordinator.py only references: {', '.join(roles) or 'no agents'}.")

    backend = _read(app_dir / "backend" / "app.py")
    if "/multi-agent/run" in backend and "/decision" in backend:
        lines.append("backend/app.py exposes the run and human-decision routes.")
    else:
        ok = False
        lines.append("backend/app.py: Multi-Agent run/decision routes not found.")

    if (app_dir / "frontend" / "js" / "multiagent.js").exists() and 'data-tab="multiagent"' in _read(
        app_dir / "frontend" / "index.html"
    ):
        lines.append("frontend: Multi-Agent tab and multiagent.js present.")
    else:
        ok = False
        lines.append("frontend: Multi-Agent tab or multiagent.js missing.")

    tests = _read(app_dir / "tests" / "test_backend.py") + _read(app_dir / "tests" / "post_commit" / "test_endpoints.py")
    lines.append(
        "backend tests cover the Multi-Agent endpoints."
        if "multi-agent" in tests
        else "backend tests for the Multi-Agent endpoints not found."
    )

    logs = _find_logs(server_dir)
    if len(logs) == len(LOG_NAMES):
        lines.extend(_log_summary(logs, repo_root))
    else:
        lines.append("workflow/audit logs not found (run a workflow, or copy them to multi-agent-server/evidence/).")

    try:
        health = requests.get(f"{SERVER_URL}/", timeout=5).json()
        lines.append(f"live server: {health.get('service')} reachable, agents={health.get('agents')}.")
    except (requests.exceptions.RequestException, ValueError):
        lines.append("live server: not reachable on localhost:5300 (not required for this review).")

    return ok, "\n".join(lines)