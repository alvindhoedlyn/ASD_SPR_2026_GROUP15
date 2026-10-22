"""Release 2 local multi-agent workflow for Budget Tracker.

Runs without Docker and preserves the existing Release 1 agent.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
import sys
from verification import run_verification


# Add the Release 1 backend to the Python import path.
BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from agentic_loop import run_budget_agent  # noqa: E402


def planner():
    return {
        "agent": "Planner",
        "tasks": [
            "Check Budget Tracker source files",
            "Run automated tests",
            "Review security scan results",
            "Request human release approval",
        ],
    }


def worker(plan, repo_root):
    required_files = [
        "student-KeyuanGan/backend/app.py",
        "student-KeyuanGan/database/app.py",
        "student-KeyuanGan/tests/test_placeholder.py",
    ]

    checks = {
        path: (repo_root / path).is_file()
        for path in required_files
    }

    verification = run_verification(repo_root)

    # Optional Release 1 AI integration.
    ai_result = {"status": "skipped", "reason": "AI integration not enabled"}

    if os.getenv("ENABLE_AI_INTEGRATION", "false").lower() == "true":
        try:
            agent_result = run_budget_agent()
            validations = agent_result.get("validation", {})
            checks_passed = all(
                validations.get(name, {}).get("status") == "passed"
                for name in ("mcp", "rag", "local_ai")
            )
            ai_result = {
                "status": "passed" if checks_passed else "failed",
                "result": agent_result,
            }
        except Exception as error:
            ai_result = {
                "status": "failed",
                "error": str(error),
            }

    return {
        "agent": "Worker",
        "plan_received": plan["tasks"],
        "file_checks": checks,
        "all_files_present": all(checks.values()),
        "verification": verification,
        "ai_integration": ai_result,
    }


def reviewer(work):
    verification = work["verification"]

    tests_passed = verification["unit_tests"]["passed"]
    ruff_passed = verification["ruff"]["passed"]
    audit_passed = verification["pip_audit"]["passed"]

    ai_status = work.get("ai_integration", {}).get("status", "skipped")
    ai_passed = ai_status in ("passed", "skipped")

    passed = (
        work["all_files_present"]
        and tests_passed
        and ruff_passed
        and audit_passed
        and ai_passed
    )

    return {
        "agent": "Reviewer",
        "status": "PASS" if passed else "FAIL",
        "reason": (
            "All required files, tests and security checks passed."
            if passed else
            "One or more required checks failed. Review Worker results."
        ),
        "tests_verified": tests_passed,
        "security_verified": ruff_passed and audit_passed,
    }



def human_review(review):
    print("\n=== HUMAN REVIEW ===")
    print(json.dumps(review, indent=2))
    print("\nThis workflow does not deploy or publish anything.")

    answer = input("Approve this review record? (yes/no): ")
    approved = answer.strip().lower() == "yes"

    return {
        "agent": "Human Review",
        "approved": approved,
        "note": "Review record approval only; not deployment approval.",
    }


def main():
    repo_root = Path(__file__).resolve().parents[2]

    plan = planner()
    work = worker(plan, repo_root)
    review = reviewer(work)

    if review["status"] == "PASS":
        human = human_review(review)
    else:
        human = {
            "agent": "Human Review",
            "approved": False,
            "note": "Blocked by reviewer failure.",
        }

    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "planner": plan,
        "worker": work,
        "reviewer": review,
        "human_review": human,
    }

    output = Path(__file__).parent / "workflow_report.json"
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("\nWorkflow report:", output)
    print("Human approved:", human["approved"])


if __name__ == "__main__":
    main()
