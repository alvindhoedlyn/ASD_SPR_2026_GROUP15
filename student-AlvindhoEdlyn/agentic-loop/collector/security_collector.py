"""Security collector for the agentic loop.

Runs the security test files (the same ones the pre-commit and post-commit
hooks run, through the same tests/pre_commit_pytest.py launcher) and returns
(ok, evidence), matching the contract of the MCP / RAG / multi-agent collectors:
  * pre-commit:  ruff, detect-secrets, pip-audit
  * post-commit: API endpoints (auth, ownership, validation) and JWT token handling

The evidence is deliberately short and safe to hand to a small local model:
  * one line per check (PASS / FAIL / ERROR / NOT RUN) with pytest's counts,
  * the failure messages (file:line + finding type, never the secret itself),
  * a WARNING line for every skipped test, because a skipped scanner means the
    check did not actually run (tool not installed, or offline for pip-audit),
  * a KNOWN GAP line for every expected failure (xfail): a documented weakness
    that is not fixed yet. These do not fail the check, but they are real
    findings, so they are shown instead of being hidden behind a green pass.
"""

import re
import subprocess  # noqa: S404 - runs only the repo's own pytest launcher
import sys
from pathlib import Path

# (label shown in the loop, test file relative to the project folder, pre-commit hook id)
CHECKS = [
    ("Ruff Scan", "tests/pre_commit/test_ruff_scan.py", "ruff-scan"),
    ("detect-secrets Scan", "tests/pre_commit/test_secrets_scan.py", "detect-secrets-scan"),
    ("pip-audit Scan", "tests/pre_commit/test_dependency_audit.py", "pip-audit-scan"),
    ("API Tests", "tests/post_commit/test_api.py", "api-tests"),
    ("Token Auth Tests (PyJWT)", "tests/post_commit/test_token_auth.py", "token-auth-tests"),
]

TIMEOUT_SECONDS = 600  # pip-audit has to reach PyPI, so allow it some time
MAX_DETAIL_LINES = 8
MAX_LINE_CHARS = 180

_COUNT_RE = re.compile(r"(\d+) (passed|failed|skipped|errors?|xfailed|xpassed)")
_ELAPSED_RE = re.compile(r" in [\d.]+s")
# Anything that looks like a key or token is replaced before it can reach the model.
_LONG_TOKEN_RE = re.compile(r"[A-Za-z0-9_\-]{32,}")


def _clean(line):
    return _LONG_TOKEN_RE.sub("[redacted]", line.strip())[:MAX_LINE_CHARS]


def _parse_counts(output):
    """Read pytest's final summary line, e.g. '1 failed, 7 passed, 6 skipped in 0.97s'."""
    for line in reversed(output.splitlines()):
        found = _COUNT_RE.findall(line)
        if found and _ELAPSED_RE.search(line):
            counts = {}
            for number, name in found:
                counts["error" if name.startswith("error") else name] = int(number)
            return counts
    return {}


def _failed_tests(output):
    """Names of failing tests from pytest's 'FAILED path::test_name[params] - msg' lines.

    Plain `assert x == y` failures carry no message, so without the test name the
    model could not tell which behaviour broke. Parameters are dropped and names
    de-duplicated, so 'test_cannot_modify_another_users_trip[...]' x4 shows once.
    """
    names = []
    for line in output.splitlines():
        if line.startswith(("FAILED ", "ERROR ")):
            test_id = line.split(" ", 1)[1].split(" - ", 1)[0]
            name = test_id.rsplit("::", 1)[-1].split("[", 1)[0].strip()
            if name and name not in names:
                names.append(name)
    return names


def _failure_details(output, project_dir):
    """Failing test names plus the assertion messages pytest prints after 'E '.

    Paths are made relative to the project folder so the model sees
    'backend/app.py:12', not a full path from this machine.
    """
    prefixes = (f"{project_dir}\\", f"{project_dir}/")
    details = [f"failed test: {name}" for name in _failed_tests(output)]
    for line in output.splitlines():
        if not line.startswith("E "):
            continue
        text = line[1:].strip()
        if text.startswith("AssertionError:"):
            text = text[len("AssertionError:"):].strip()
            if text.endswith(":"):  # a header such as "Security findings:" carries no information
                continue
        if not text or text.startswith(("assert ", "+", "where ")):
            continue
        for prefix in prefixes:
            text = text.replace(prefix, "")
        text = _clean(text)
        if text not in details:
            details.append(text)
    return details[:MAX_DETAIL_LINES]


def _known_gaps(output):
    """Expected failures (xfail): 'XFAIL tests/...::test_name - Known gap: reason'."""
    gaps = []
    for line in output.splitlines():
        if line.startswith("XFAIL ") and " - " in line:
            reason = line.split(" - ", 1)[1].strip()
            if reason.lower().startswith("known gap:"):
                reason = reason[len("known gap:"):].strip()
            reason = _clean(reason)
            if reason not in gaps:
                gaps.append(reason)
    return gaps


def _skip_reasons(output):
    reasons = []
    for line in output.splitlines():
        if line.startswith("SKIPPED ["):
            reason = _clean(line.rsplit(": ", 1)[-1])
            if reason not in reasons:
                reasons.append(reason)
    return reasons


def _run_check(project_dir, launcher, test_path):
    """Returns (status, summary, details, warnings, gaps) for one security test file."""
    cmd = [
        sys.executable, str(launcher), test_path,
        "-q", "--tb=short", "-rfEsx", "-p", "no:cacheprovider",
    ]
    try:
        proc = subprocess.run(  # noqa: S603 - fixed arguments, repo-controlled launcher
            cmd,
            cwd=project_dir,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return "ERROR", f"timed out after {TIMEOUT_SECONDS}s", [], [], []

    output = f"{proc.stdout}\n{proc.stderr}"
    counts = _parse_counts(output)
    summary = ", ".join(f"{number} {name}" for name, number in counts.items()) or "no test summary"
    warnings = _skip_reasons(output)
    gaps = _known_gaps(output)

    if proc.returncode not in (0, 1) or not counts:
        tail = [_clean(line) for line in output.strip().splitlines()[-3:] if line.strip()]
        return "ERROR", f"pytest could not run it (exit code {proc.returncode})", tail, warnings, gaps

    if counts.get("failed", 0) or counts.get("error", 0):
        return "FAIL", summary, _failure_details(output, project_dir), warnings, gaps
    if not counts.get("passed", 0):
        return "NOT RUN", summary, [], warnings, gaps
    return "PASS", summary, [], warnings, gaps


def collect(agentic_loop_dir, repo_root):
    """Shared collector contract: returns (ok: bool, evidence: str).

    agentic_loop_dir is student-AlvindhoEdlyn/agentic-loop, so the project
    folder (where tests/ and pyproject.toml live) is its parent. repo_root is
    accepted for the shared signature and is not needed here.
    """
    project_dir = Path(agentic_loop_dir).resolve().parent
    launcher = project_dir / "tests" / "pre_commit_pytest.py"
    if not launcher.exists():
        return False, f"ERROR: security test launcher not found at tests/pre_commit_pytest.py in {project_dir}"

    lines = []
    passed_checks = 0
    known_gaps = 0
    for label, test_path, hook_id in CHECKS:
        status, summary, details, warnings, gaps = _run_check(project_dir, launcher, test_path)
        lines.append(f"{label} (hook {hook_id}): {status} - {summary}")
        lines.extend(f"  finding: {detail}" for detail in details)
        lines.extend(f"  WARNING: skipped - {reason}" for reason in warnings)
        lines.extend(f"  KNOWN GAP: {gap}" for gap in gaps)
        known_gaps += len(gaps)
        if status == "PASS":
            passed_checks += 1

    summary_line = f"Summary: {passed_checks} of {len(CHECKS)} security checks passed"
    if known_gaps:
        summary_line += f", {known_gaps} known gaps documented but not fixed"
    lines.append(summary_line)
    return passed_checks == len(CHECKS), "\n".join(lines)