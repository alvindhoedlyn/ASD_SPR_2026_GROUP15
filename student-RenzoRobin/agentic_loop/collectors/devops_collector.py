"""
DevOps evidence collector for the Accommodation Recommender pipeline.

Pure code, no LLM calls. Reads real files off disk and reports back
factual evidence — the OBSERVE stage of the agentic loop. Adapted from
the ASD course's Lab 05 devops_collector.py pattern, pointed at this
project's actual workflow, compose file, and test suite instead of a
generic enrolment-app.
"""
from pathlib import Path

REQUIRED_WORKFLOW_JOBS = ["test", "docker-build"]
REQUIRED_COMPOSE_SERVICES = [
    "student-RenzoRobin-frontend",
    "student-RenzoRobin-backend",
    "student-RenzoRobin-database",
]
REQUIRED_TEST_FILES = ["test_backend.py", "test_database.py"]


def collect(app_dir: Path, repo_root: Path) -> tuple[bool, str]:
    """
    app_dir:   student-RenzoRobin/  (this student's feature folder)
    repo_root: the repository root (where docker-compose.yml and
               .github/workflows/ live)
    """
    workflow_path = repo_root / ".github" / "workflows" / "student-3-ci.yml"
    compose_path = repo_root / "docker-compose.yml"
    tests_dir = app_dir / "tests"

    required_paths = [workflow_path, compose_path, tests_dir]
    missing: list[str] = []
    for path in required_paths:
        if not path.exists():
            missing.append(_relative_label(path, repo_root, app_dir))

    if missing:
        return False, "DevOps evidence incomplete. Missing: " + ", ".join(missing)

    workflow_text = workflow_path.read_text(encoding="utf-8")
    compose_text = compose_path.read_text(encoding="utf-8")

    missing_jobs = [job for job in REQUIRED_WORKFLOW_JOBS if f"{job}:" not in workflow_text.replace(" ", "")]
    missing_services = [svc for svc in REQUIRED_COMPOSE_SERVICES if svc not in compose_text]
    missing_tests = [f for f in REQUIRED_TEST_FILES if not (tests_dir / f).exists()]

    if missing_jobs:
        return False, "Workflow missing required jobs: " + ", ".join(missing_jobs)
    if missing_services:
        return False, "docker-compose.yml missing required services: " + ", ".join(missing_services)
    if missing_tests:
        return False, "Missing test files: " + ", ".join(missing_tests)

    has_test_step = "pytest" in workflow_text
    has_path_scoped_trigger = "student-RenzoRobin/**" in workflow_text
    has_docker_build_needs_test = "needs: test" in workflow_text.replace(" ", "") or "needs:\n    - test" in workflow_text

    test_step_text = "includes" if has_test_step else "does NOT include"
    trigger_text = "is" if has_path_scoped_trigger else "is NOT"

    evidence = (
        "DevOps evidence: workflow defines jobs "
        f"{', '.join(REQUIRED_WORKFLOW_JOBS)}; "
        f"test step {test_step_text} an automated pytest run; "
        f"trigger {trigger_text} path-scoped to student-RenzoRobin/**; "
        f"docker-compose.yml defines all 3 required services "
        f"({', '.join(REQUIRED_COMPOSE_SERVICES)}); "
        f"test suite present: {', '.join(REQUIRED_TEST_FILES)}."
    )
    return True, evidence


def _relative_label(path: Path, repo_root: Path, app_dir: Path) -> str:
    try:
        return str(path.relative_to(repo_root))
    except ValueError:
        try:
            return str(path.relative_to(app_dir))
        except ValueError:
            return str(path)