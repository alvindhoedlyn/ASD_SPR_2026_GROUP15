"""
Testing review collector: pre-commit security scans and post-commit endpoint tests.

Runs each scan/test file with pytest, records the result line, checks that the hooks and
the CI workflow are configured, and writes everything to reports/testing-evidence.md so
the evidence is kept with the project.

Returns (ok, evidence) like the other collectors.
"""
import subprocess  # noqa: S404 - runs pytest and the GitHub CLI with fixed arguments
import sys
from datetime import datetime, timezone
from pathlib import Path

SUITES = (
    ("Ruff security scan", "tests/pre_commit/test_ruff_scan.py"),
    ("detect-secrets scan", "tests/pre_commit/test_secrets_scan.py"),
    ("pip-audit dependency scan", "tests/pre_commit/test_dependency_audit.py"),
    ("Post-commit endpoint tests", "tests/post_commit/test_endpoints.py"),
)
HOOK_IDS = ("ruff-scan", "detect-secrets-scan", "pip-audit-scan", "endpoint-tests")
CI_WORKFLOW = ".github/workflows/student-3-ci.yml"
SUITE_TIMEOUT_SECONDS = 900


def _run_suite(app_dir: Path, test_path: str) -> tuple[bool, str]:
    command = [sys.executable, "-m", "pytest", test_path, "-q", "-p", "no:cacheprovider"]
    try:
        proc = subprocess.run(  # noqa: S603 - fixed arguments, interpreter is sys.executable
            command, cwd=app_dir, capture_output=True, text=True,
            timeout=SUITE_TIMEOUT_SECONDS, check=False,
        )
    except subprocess.TimeoutExpired:
        return False, f"timed out after {SUITE_TIMEOUT_SECONDS}s"
    output = [line for line in proc.stdout.strip().splitlines() if line.strip()]
    return proc.returncode == 0, (output[-1] if output else "no output")


def _recent_ci_runs(repo_root: Path) -> str:
    command = ["gh", "run", "list", "--workflow", "student-3-ci.yml", "--limit", "3",
               "--json", "conclusion,displayTitle"]
    try:
        proc = subprocess.run(  # noqa: S603, S607 - GitHub CLI from PATH, fixed arguments
            command, cwd=repo_root, capture_output=True, text=True, timeout=30, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "GitHub CLI not available, so recent CI runs were not read."
    if proc.returncode != 0:
        return "GitHub CLI could not list CI runs (not logged in?)."
    return f"recent student-3-ci.yml runs: {proc.stdout.strip()}"


def collect(app_dir: Path, repo_root: Path) -> tuple[bool, str]:
    lines, ok = [], True

    config = app_dir / ".pre-commit-config.yaml"
    config_text = config.read_text(encoding="utf-8") if config.exists() else ""
    absent = [hook for hook in HOOK_IDS if f"id: {hook}" not in config_text]
    if absent:
        ok = False
        lines.append("pre-commit config: missing hooks " + ", ".join(absent) + ".")
    else:
        lines.append("pre-commit config: ruff-scan, detect-secrets-scan, pip-audit-scan and endpoint-tests hooks configured.")

    workflow = repo_root / CI_WORKFLOW
    workflow_text = workflow.read_text(encoding="utf-8") if workflow.exists() else ""
    if "tests/post_commit" in workflow_text:
        lines.append("student-3-ci.yml runs the post-commit endpoint tests.")
    else:
        ok = False
        lines.append("student-3-ci.yml does not run tests/post_commit.")

    passed_count = 0
    for name, path in SUITES:
        passed, summary = _run_suite(app_dir, path)
        passed_count += passed
        ok = ok and passed
        lines.append(f"{name} ({path}): {'PASS' if passed else 'FAIL'} - {summary}")

    lines.append(f"RULE CHECK: {passed_count} of {len(SUITES)} test suites passed.")
    lines.append(_recent_ci_runs(repo_root))

    evidence = "\n".join(lines)
    reports = app_dir / "reports"
    reports.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    (reports / "testing-evidence.md").write_text(
        f"# Testing evidence\n\nCollected: {stamp}\n\n```text\n{evidence}\n```\n", encoding="utf-8"
    )
    return ok, evidence