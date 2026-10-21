"""Collect Student 5 workflow history and coordination/audit evidence."""

import json
from pathlib import Path


LOG_NAMES = ("workflow_history.jsonl", "coordination_audit.jsonl")


def read_json_lines(path):
    if not path.exists():
        return []
    records = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        try:
            records.append(json.loads(line))
        except ValueError:
            continue
    return records


def clean_block(value):
    return "\n".join(line.rstrip() for line in str(value or "").splitlines())


def find_log(server_directory, filename):
    for directory in (server_directory / "data", server_directory / "evidence", server_directory):
        candidate = directory / filename
        if candidate.exists():
            return candidate
    return server_directory / "missing" / filename


def collect(app_dir: Path, repo_root: Path):
    server = repo_root / "ai-services" / "multi-agent-server"
    required = (
        server / "app.py",
        server / "coordinator.py",
        server / "agents" / "planner_agent.py",
        server / "agents" / "worker_agent.py",
        server / "agents" / "reviewer_agent.py",
        app_dir / "backend" / "app.py",
        app_dir / "frontend" / "index.html",
        app_dir / "tests" / "post_commit" / "test_multi_agent_endpoints.py",
    )
    missing = [str(path.relative_to(repo_root)) for path in required if not path.exists()]

    history = read_json_lines(find_log(server, LOG_NAMES[0]))
    audits = read_json_lines(find_log(server, LOG_NAMES[1]))
    latest_by_id = {}
    for record in history:
        if record.get("caller") == "student-5" or record.get("feature") == "flight-recommender":
            latest_by_id[record.get("workflow_id")] = record

    lines = [
        "Required integration files: " + ("PASS" if not missing else "FAIL"),
        "Missing files: " + (", ".join(missing) if missing else "none"),
        f"Student 5 workflows found: {len(latest_by_id)}",
    ]
    if not latest_by_id:
        lines.append("Completed Planner -> Worker -> Reviewer -> Human Review evidence: FAIL (run and decide a workflow).")
        return False, "\n".join(lines)

    workflow = list(latest_by_id.values())[-1]
    workflow_id = workflow.get("workflow_id")
    steps = workflow.get("steps", {})
    agent_complete = all(steps.get(name, {}).get("status") in {"ok", "fallback"} for name in ("planner", "worker", "reviewer"))
    human_complete = workflow.get("human_decision", {}).get("status") not in {None, "pending"}
    events = [row.get("event") for row in audits if row.get("workflow_id") == workflow_id]
    relevant_audits = [row for row in audits if row.get("workflow_id") == workflow_id]
    audit_complete = all(
        event in events
        for event in ("workflow_created", "agent_step_completed", "awaiting_human_review", "human_decision")
    )
    lines.extend([
        f"Latest workflow ID: {workflow_id}",
        f"Planner, Worker and Reviewer completed: {'PASS' if agent_complete else 'FAIL'}",
        f"Human review completed: {'PASS' if human_complete else 'FAIL'}",
        f"Coordination audit complete: {'PASS' if audit_complete else 'FAIL'}",
        f"Final status: {workflow.get('status')}",
    ])

    report_directory = app_dir / "reports"
    report_directory.mkdir(exist_ok=True)
    evidence_directory = report_directory / "evidence"
    evidence_directory.mkdir(exist_ok=True)
    (evidence_directory / "workflow-history.json").write_text(
        json.dumps(workflow, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (evidence_directory / "coordination-audit.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in relevant_audits),
        encoding="utf-8",
    )
    (report_directory / "multi-agent-evidence.md").write_text(
        "# Student 5 Multi-Agent Workflow Evidence\n\n"
        + "\n".join(f"- {line}" for line in lines)
        + "\n\n## Agent outputs\n\n"
        + "\n\n".join(
            f"### {name.title()}\n\n```text\n{clean_block(steps.get(name, {}).get('output'))}\n```"
            for name in ("planner", "worker", "reviewer")
        )
        + "\n\n## Human review\n\n```json\n"
        + json.dumps(workflow.get("human_decision", {}), indent=2)
        + "\n```\n\n## Coordination audit\n\n"
        + "\n".join(
            f"- {row.get('ts')} — `{row.get('event')}`"
            + (f" ({row.get('agent')})" if row.get("agent") else "")
            for row in relevant_audits
        )
        + "\n\nRaw copies: `reports/evidence/workflow-history.json` and "
        + "`reports/evidence/coordination-audit.jsonl`.\n",
        encoding="utf-8",
    )
    ok = not missing and agent_complete and human_complete and audit_complete
    return ok, "\n".join(lines)
