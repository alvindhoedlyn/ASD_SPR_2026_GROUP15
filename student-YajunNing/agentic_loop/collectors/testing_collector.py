"""Execute Student 5 security hooks and two post-commit endpoint tests."""

import subprocess  # noqa: S404
import sys
from datetime import datetime, timezone
from pathlib import Path


HOOKS = ("ruff-scan", "detect-secrets-scan", "pip-audit-scan")
POST_COMMIT_TEST = "student-YajunNing/tests/post_commit/test_multi_agent_endpoints.py"


def run(command, cwd):
    try:
        result = subprocess.run(  # noqa: S603
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=900,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return False, "Timed out after 900 seconds"
    output = [line.strip() for line in (result.stdout + "\n" + result.stderr).splitlines() if line.strip()]
    return result.returncode == 0, output[-1] if output else "No output"


def collect(app_dir: Path, repo_root: Path):
    lines = []
    ok = True
    config = app_dir / ".pre-commit-config.yaml"
    if not config.exists():
        return False, "Student 5 pre-commit configuration is missing."

    for hook in HOOKS:
        passed, summary = run(
            [
                sys.executable,
                "-m",
                "pre_commit",
                "run",
                "--config",
                "student-YajunNing/.pre-commit-config.yaml",
                hook,
                "--all-files",
            ],
            repo_root,
        )
        ok = ok and passed
        lines.append(f"{hook}: {'PASS' if passed else 'FAIL'} - {summary}")

    endpoint_passed, endpoint_summary = run(
        [sys.executable, "-m", "pytest", POST_COMMIT_TEST, "-q", "-p", "no:cacheprovider"],
        repo_root,
    )
    ok = ok and endpoint_passed
    lines.append(f"two post-commit endpoint functions: {'PASS' if endpoint_passed else 'FAIL'} - {endpoint_summary}")

    workflow = (repo_root / ".github" / "workflows" / "student-5-ci.yml").read_text(encoding="utf-8")
    for label, marker in (
        ("endpoint test path", POST_COMMIT_TEST),
        ("JUnit evidence", "--junitxml"),
        ("artifact upload", "upload-artifact"),
    ):
        present = marker in workflow
        ok = ok and present
        lines.append(f"CI {label}: {'PASS' if present else 'FAIL'}")

    actions_evidence = app_dir / "reports" / "github-actions-evidence.md"
    actions_text = actions_evidence.read_text(encoding="utf-8") if actions_evidence.exists() else ""
    actions_passed = "Conclusion: `success`" in actions_text and "student-5-post-commit-evidence" in actions_text
    ok = ok and actions_passed
    lines.append(
        "GitHub Actions run and artifact evidence: "
        + ("PASS" if actions_passed else "FAIL - collect after pushing this branch")
    )
    lines.append(f"Overall local testing decision: {'PASS' if ok else 'FAIL'}")

    reports = app_dir / "reports"
    reports.mkdir(exist_ok=True)
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    (reports / "testing-evidence.md").write_text(
        "# Student 5 Testing Evidence\n\n"
        f"Collected: {timestamp}\n\n```text\n" + "\n".join(lines) + "\n```\n",
        encoding="utf-8",
    )
    return ok, "\n".join(lines)
