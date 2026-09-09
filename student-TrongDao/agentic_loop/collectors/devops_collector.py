from pathlib import Path


REQUIRED_WORKFLOW_JOBS = [
    "test",
    "docker-build"
]

REQUIRED_COMPOSE_SERVICES = [
    "student-TrongDao",
    "student-TrongDao-backend",
    "student-TrongDao-database",
    "ai-mode"
]

REQUIRED_TEST_FILES = [
    "test_backend.py",
    "test_database.py"
]


def collect(
    app_dir: Path,
    repo_root: Path
):
    workflow_path = (
        repo_root
        / ".github"
        / "workflows"
        / "student-4-ci.yml"
    )

    compose_path = repo_root / "docker-compose.yml"
    tests_directory = app_dir / "tests"

    required_paths = [
        workflow_path,
        compose_path,
        tests_directory
    ]

    missing_paths = []

    for path in required_paths:
        if not path.exists():
            missing_paths.append(str(path))

    if missing_paths:
        return False, (
            "DevOps evidence is incomplete. Missing: "
            + ", ".join(missing_paths)
        )

    workflow_text = workflow_path.read_text(
        encoding="utf-8"
    )

    compose_text = compose_path.read_text(
        encoding="utf-8"
    )

    compact_workflow = workflow_text.replace(" ", "")

    missing_jobs = []

    for job in REQUIRED_WORKFLOW_JOBS:
        if f"{job}:" not in compact_workflow:
            missing_jobs.append(job)

    if missing_jobs:
        return False, (
            "GitHub Actions workflow is missing jobs: "
            + ", ".join(missing_jobs)
        )

    missing_services = []

    for service in REQUIRED_COMPOSE_SERVICES:
        if service not in compose_text:
            missing_services.append(service)

    if missing_services:
        return False, (
            "Docker Compose is missing services: "
            + ", ".join(missing_services)
        )

    missing_tests = []

    for test_file in REQUIRED_TEST_FILES:
        if not (tests_directory / test_file).exists():
            missing_tests.append(test_file)

    if missing_tests:
        return False, (
            "The test folder is missing: "
            + ", ".join(missing_tests)
        )

    has_pytest = "pytest" in workflow_text

    has_path_trigger = (
        "student-TrongDao/**" in workflow_text
    )

    docker_waits_for_tests = (
        "needs:test" in compact_workflow
    )

    builds_frontend = "--target frontend" in workflow_text
    builds_backend = "--target backend" in workflow_text
    builds_database = "--target database" in workflow_text

    has_qwen = "qwen2.5:0.5b" in compose_text
    has_llama = "llama3.1:8b" in compose_text

    evidence = (
        "DevOps evidence collected from student-4-ci.yml and "
        "docker-compose.yml. "
        f"Workflow jobs found: {', '.join(REQUIRED_WORKFLOW_JOBS)}. "
        f"Pytest included: {has_pytest}. "
        f"Path trigger configured: {has_path_trigger}. "
        f"Docker build waits for tests: {docker_waits_for_tests}. "
        f"Frontend target found: {builds_frontend}. "
        f"Backend target found: {builds_backend}. "
        f"Database target found: {builds_database}. "
        f"Required Compose services found: "
        f"{', '.join(REQUIRED_COMPOSE_SERVICES)}. "
        f"Qwen configured: {has_qwen}. "
        f"Llama configured: {has_llama}. "
        f"Test files found: {', '.join(REQUIRED_TEST_FILES)}."
    )

    return True, evidence