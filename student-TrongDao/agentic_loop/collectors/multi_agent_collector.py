"""Collect Student 4 Multi-Agent workflow and audit evidence."""

import json
from collections import Counter
from pathlib import Path

import requests


SERVER_URL = "http://localhost:5300"
LOG_FILENAMES = (
    "workflow_history.jsonl",
    "coordination_audit.jsonl"
)
SERVER_FILES = (
    "app.py",
    "coordinator.py",
    "evidence.py",
    "agents/planner_agent.py",
    "agents/worker_agent.py",
    "agents/reviewer_agent.py",
    "prompts/planner.txt",
    "prompts/worker.txt",
    "prompts/reviewer.txt"
)


def read_text(path):
    if not path.exists():
        return ""

    return path.read_text(
        encoding="utf-8",
        errors="ignore"
    )


def read_json_lines(path):
    records = []

    for line in read_text(path).splitlines():
        try:
            records.append(json.loads(line))
        except ValueError:
            continue

    return records


def find_log_files(server_directory):
    found = {}

    for directory in (
        server_directory / "data",
        server_directory / "evidence",
        server_directory
    ):
        for filename in LOG_FILENAMES:
            candidate = directory / filename

            if filename not in found and candidate.exists():
                found[filename] = candidate

    return found


def student_workflows(history):
    latest_by_id = {}

    for record in history:
        is_student_four = (
            record.get("caller") == "student-4"
            or record.get("feature")
            == "location-recommender"
        )

        if is_student_four and record.get("workflow_id"):
            latest_by_id[record["workflow_id"]] = record

    return list(latest_by_id.values())


def step_summary(step_name, step):
    output = str(step.get("output", "")).strip()

    return (
        f"{step_name.title()}: "
        f"status={step.get('status')}, "
        f"model={step.get('model')}, "
        f"elapsed_ms={step.get('elapsed_ms')}\n"
        f"{output}"
    )


def write_evidence_report(
    app_directory,
    workflow,
    audit_records,
    evidence
):
    reports_directory = app_directory / "reports"
    reports_directory.mkdir(exist_ok=True)

    workflow_id = workflow.get("workflow_id")
    relevant_audit = [
        record
        for record in audit_records
        if record.get("workflow_id") == workflow_id
    ]

    steps = workflow.get("steps", {})
    human_decision = workflow.get("human_decision", {})

    report_lines = [
        "# Student 4 Multi-Agent Workflow Evidence",
        "",
        f"- Workflow ID: `{workflow_id}`",
        f"- Request: {workflow.get('user_request')}",
        f"- Status: `{workflow.get('status')}`",
        f"- Evidence records: {workflow.get('evidence_count')}",
        f"- Degraded execution: {workflow.get('degraded')}",
        "",
        "## Agent outputs",
        ""
    ]

    for step_name in ("planner", "worker", "reviewer"):
        report_lines.extend([
            f"### {step_name.title()}",
            "",
            "```text",
            step_summary(
                step_name,
                steps.get(step_name, {})
            ),
            "```",
            ""
        ])

    report_lines.extend([
        "## Human review",
        "",
        f"- Decision: `{human_decision.get('decision')}`",
        f"- Status: `{human_decision.get('status')}`",
        f"- Note: {human_decision.get('note') or 'None'}",
        "- Corrected output: "
        + (
            human_decision.get("corrected_output")
            or "None"
        ),
        "",
        "## Coordination audit",
        ""
    ])

    for record in relevant_audit:
        report_lines.append(
            "- "
            f"{record.get('ts')} — "
            f"{record.get('event')}"
            + (
                f" ({record.get('agent')})"
                if record.get("agent")
                else ""
            )
        )

    report_lines.extend([
        "",
        "## Review evidence summary",
        "",
        "```text",
        evidence,
        "```",
        ""
    ])

    report_path = (
        reports_directory / "multi-agent-evidence.md"
    )

    report_path.write_text(
        "\n".join(report_lines),
        encoding="utf-8"
    )


def collect(app_dir: Path, repo_root: Path):
    evidence_lines = []
    all_checks_passed = True
    server_directory = (
        repo_root / "ai-services" / "multi-agent-server"
    )

    missing_server_files = [
        filename
        for filename in SERVER_FILES
        if not (server_directory / filename).exists()
    ]

    if missing_server_files:
        all_checks_passed = False
        evidence_lines.append(
            "Multi-Agent Server files missing: "
            + ", ".join(missing_server_files)
        )
    else:
        evidence_lines.append(
            "Multi-Agent Server files: PASS"
        )

    backend_text = read_text(app_dir / "backend" / "app.py")
    frontend_html = read_text(
        app_dir / "frontend" / "index.html"
    )
    frontend_script = read_text(
        app_dir / "frontend" / "js" / "location.js"
    )
    endpoint_tests = read_text(
        app_dir
        / "tests"
        / "post_commit"
        / "test_multi_agent_endpoints.py"
    )

    integration_checks = {
        "backend run route": (
            "/api/multi-agent/run" in backend_text
        ),
        "backend human-decision route": (
            "/decision" in backend_text
        ),
        "frontend workflow form": (
            'id="multi-agent-form"' in frontend_html
        ),
        "frontend human-review form": (
            'id="human-decision-form"' in frontend_html
        ),
        "frontend workflow request": (
            "/api/multi-agent/run" in frontend_script
        ),
        "post-commit endpoint tests": (
            "test_run_multi_agent_workflow_endpoint"
            in endpoint_tests
            and "test_record_human_decision_endpoint"
            in endpoint_tests
        )
    }

    for label, passed in integration_checks.items():
        all_checks_passed = all_checks_passed and passed
        evidence_lines.append(
            f"{label}: " + ("PASS" if passed else "FAIL")
        )

    log_files = find_log_files(server_directory)
    history = read_json_lines(
        log_files.get(
            "workflow_history.jsonl",
            Path("missing")
        )
    )
    audit_records = read_json_lines(
        log_files.get(
            "coordination_audit.jsonl",
            Path("missing")
        )
    )
    workflows = student_workflows(history)

    if not workflows:
        return False, (
            "\n".join(evidence_lines)
            + "\nNo Student 4 workflow history was found."
        )

    latest = workflows[-1]
    workflow_id = latest.get("workflow_id")
    steps = latest.get("steps", {})
    human_decision = latest.get("human_decision", {})

    completed_agents = [
        name
        for name in ("planner", "worker", "reviewer")
        if steps.get(name, {}).get("status")
        in ("ok", "fallback")
    ]
    agent_statuses = Counter(
        step.get("status")
        for step in steps.values()
    )
    workflow_audit = [
        record
        for record in audit_records
        if record.get("workflow_id") == workflow_id
    ]
    audit_events = Counter(
        record.get("event")
        for record in workflow_audit
    )

    agents_complete = len(completed_agents) == 3
    human_complete = (
        human_decision.get("status") != "pending"
    )
    audit_complete = all(
        audit_events.get(event, 0) >= minimum
        for event, minimum in {
            "workflow_created": 1,
            "agent_step_completed": 3,
            "awaiting_human_review": 1,
            "human_decision": 1
        }.items()
    )

    all_checks_passed = (
        all_checks_passed
        and agents_complete
        and human_complete
        and audit_complete
    )

    evidence_lines.extend([
        f"Student 4 workflows found: {len(workflows)}",
        f"Latest workflow ID: {workflow_id}",
        f"Evidence records: {latest.get('evidence_count')}",
        f"Agent sequence complete: {agents_complete}",
        f"Agent statuses: {dict(agent_statuses)}",
        f"Degraded execution: {latest.get('degraded')}",
        f"Human decision complete: {human_complete}",
        "Human decision: "
        f"{human_decision.get('decision')} "
        f"({human_decision.get('status')})",
        f"Audit events: {dict(audit_events)}",
        f"Coordination audit complete: {audit_complete}"
    ])

    reviewer_output = str(
        steps.get("reviewer", {}).get("output", "")
    ).casefold()

    if (
        human_decision.get("decision") == "accept"
        and "recommendation: deny" in reviewer_output
    ):
        evidence_lines.append(
            "Risk: the human accepted the workflow despite "
            "the reviewer recommending denial."
        )

    try:
        response = requests.get(
            f"{SERVER_URL}/",
            timeout=5
        )
        response.raise_for_status()
        evidence_lines.append(
            "Live Multi-Agent Server: PASS"
        )
    except requests.RequestException:
        evidence_lines.append(
            "Live Multi-Agent Server: unavailable; "
            "persisted evidence was used."
        )

    evidence_lines.append(
        "Overall workflow evidence: "
        + ("PASS" if all_checks_passed else "FAIL")
    )

    evidence = "\n".join(evidence_lines)

    write_evidence_report(
        app_dir,
        latest,
        audit_records,
        evidence
    )

    return all_checks_passed, evidence
