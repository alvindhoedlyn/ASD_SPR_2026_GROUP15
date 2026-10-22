"""Release 2 local multi-agent workflow for Budget Tracker.

Runs without Docker and preserves the existing Release 1 agent.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from verification import run_verification


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

    return {
        "agent": "Worker",
        "plan_received": plan["tasks"],
        "file_checks": checks,
        "all_files_present": all(checks.values()),
        "verification": verification,
    }


def reviewer(work):
    verification = work["verification"]

    tests_passed = verification["unit_tests"]["passed"]
    ruff_passed = verification["ruff"]["passed"]
    audit_passed = verification["pip_audit"]["passed"]

    passed = (
        work["all_files_present"]
        and tests_passed
        and ruff_passed
        and audit_passed
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
