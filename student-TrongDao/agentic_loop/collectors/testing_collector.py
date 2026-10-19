"""Collect Student 4 security and endpoint-testing evidence."""

import subprocess  # noqa: S404
import sys
from datetime import datetime, timezone
from pathlib import Path


HOOKS = (
    ("Ruff security scan", "ruff-scan"),
    ("detect-secrets scan", "detect-secrets-scan"),
    ("pip-audit dependency scan", "pip-audit-scan")
)

POST_COMMIT_TEST = (
    "student-TrongDao/tests/post_commit/"
    "test_multi_agent_endpoints.py"
)

WORKFLOW = ".github/workflows/student-4-ci.yml"
TIMEOUT_SECONDS = 900


def run_command(command, working_directory):
    try:
        result = subprocess.run(  # noqa: S603
            command,
            cwd=working_directory,
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
            check=False
        )
    except subprocess.TimeoutExpired:
        return False, (
            f"Timed out after {TIMEOUT_SECONDS} seconds"
        )

    output_lines = [
        line.strip()
        for line in (
            result.stdout + "\n" + result.stderr
        ).splitlines()
        if line.strip()
    ]

    summary = (
        output_lines[-1]
        if output_lines
        else "No command output"
    )

    return result.returncode == 0, summary


def collect(app_dir: Path, repo_root: Path):
    evidence_lines = []
    all_checks_passed = True

    pre_commit_config = (
        app_dir / ".pre-commit-config.yaml"
    )

    if not pre_commit_config.exists():
        return False, (
            "Student 4 pre-commit configuration is missing."
        )

    config_text = pre_commit_config.read_text(
        encoding="utf-8"
    )

    missing_hooks = [
        hook_id
        for _, hook_id in HOOKS
        if f"id: {hook_id}" not in config_text
    ]

    if missing_hooks:
        all_checks_passed = False
        evidence_lines.append(
            "Missing pre-commit hooks: "
            + ", ".join(missing_hooks)
        )
    else:
        evidence_lines.append(
            "Required pre-commit hooks are configured."
        )

    for scan_name, hook_id in HOOKS:
        command = [
            sys.executable,
            "-m",
            "pre_commit",
            "run",
            "--config",
            "student-TrongDao/.pre-commit-config.yaml",
            hook_id,
            "--all-files"
        ]

        passed, summary = run_command(
            command,
            repo_root
        )

        all_checks_passed = (
            all_checks_passed and passed
        )

        result_label = "PASS" if passed else "FAIL"

        evidence_lines.append(
            f"{scan_name}: {result_label} - {summary}"
        )

    endpoint_command = [
        sys.executable,
        "-m",
        "pytest",
        POST_COMMIT_TEST,
        "-q",
        "-p",
        "no:cacheprovider"
    ]

    endpoints_passed, endpoint_summary = run_command(
        endpoint_command,
        repo_root
    )

    all_checks_passed = (
        all_checks_passed and endpoints_passed
    )

    endpoint_label = (
        "PASS" if endpoints_passed else "FAIL"
    )

    evidence_lines.append(
        "Post-commit endpoint tests: "
        f"{endpoint_label} - {endpoint_summary}"
    )

    workflow_path = repo_root / WORKFLOW

    if not workflow_path.exists():
        all_checks_passed = False
        evidence_lines.append(
            "Student 4 CI workflow is missing."
        )
    else:
        workflow_text = workflow_path.read_text(
            encoding="utf-8"
        )

        workflow_checks = {
            "endpoint test path": (
                POST_COMMIT_TEST in workflow_text
            ),
            "JUnit evidence": (
                "--junitxml" in workflow_text
            ),
            "artifact upload": (
                "upload-artifact" in workflow_text
            )
        }

        for label, passed in workflow_checks.items():
            all_checks_passed = (
                all_checks_passed and passed
            )

            evidence_lines.append(
                f"CI {label}: "
                + ("PASS" if passed else "FAIL")
            )

    evidence_lines.append(
        "Overall testing decision: "
        + (
            "PASS"
            if all_checks_passed
            else "FAIL"
        )
    )

    evidence = "\n".join(evidence_lines)

    reports_directory = app_dir / "reports"
    reports_directory.mkdir(exist_ok=True)

    timestamp = datetime.now(
        timezone.utc
    ).isoformat(timespec="seconds")

    report_path = (
        reports_directory / "testing-evidence.md"
    )

    report_path.write_text(
        (
            "# Student 4 Testing Evidence\n\n"
            f"Collected: {timestamp}\n\n"
            "```text\n"
            f"{evidence}\n"
            "```\n"
        ),
        encoding="utf-8"
    )

    return all_checks_passed, evidence  