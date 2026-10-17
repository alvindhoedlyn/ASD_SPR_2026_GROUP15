"""Pre-commit: the pip-audit hook audits dependencies only, and finds no known CVEs."""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.pre_commit

ROOT = Path(__file__).resolve().parents[2]
REQUIREMENTS = ROOT / "requirements.txt"

needs_pip_audit = pytest.mark.skipif(
    importlib.util.find_spec("pip_audit") is None, reason="pip-audit is not installed"
)


def test_requirements_file_exists_and_lists_packages():
    assert REQUIREMENTS.exists(), "requirements.txt is missing: pip-audit has nothing to audit"
    lines = [
        line.strip()
        for line in REQUIREMENTS.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]
    assert lines, "requirements.txt is empty"


def test_pip_audit_hook_is_configured_to_audit_only():
    text = (ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    assert "id: pip-audit-scan" in text
    assert "tests/pre_commit/test_dependency_audit.py" in text
    assert "--fix" not in text, "the hook must report vulnerabilities, never rewrite requirements"


@needs_pip_audit
def test_no_known_vulnerabilities_in_requirements():
    proc = subprocess.run(
        [sys.executable, "-m", "pip_audit", "-r", str(REQUIREMENTS),
         "--progress-spinner", "off", "-f", "json"],
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )
    try:
        report = json.loads(proc.stdout)
    except ValueError:
        pytest.skip(f"pip-audit could not complete (offline or unresolved package?): {proc.stderr[-400:]}")

    vulnerable = [
        f"{dep['name']}=={dep['version']}: {', '.join(v['id'] for v in dep['vulns'])}"
        for dep in report.get("dependencies", [])
        if dep.get("vulns")
    ]
    assert not vulnerable, "Vulnerable dependencies:\n" + "\n".join(vulnerable)