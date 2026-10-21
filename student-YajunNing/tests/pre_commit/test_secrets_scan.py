"""Verify that Student 5 source files contain no detected secrets."""

import json
import subprocess  # noqa: S404
import sys
from pathlib import Path

import pytest


pytestmark = pytest.mark.pre_commit
ROOT = Path(__file__).resolve().parents[2]


def test_detect_secrets_hook_is_configured():
    config = (ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    assert "id: detect-secrets-scan" in config


def test_no_secrets_in_student_5_source():
    result = subprocess.run(  # noqa: S603
        [
            sys.executable,
            "-m",
            "detect_secrets",
            "scan",
            "--all-files",
            "--exclude-files",
            r"(^|/)(\.pytest_cache|\.ruff_cache|__pycache__|flight-hero-sunset\.png)(/|$)",
            ".",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    findings = json.loads(result.stdout).get("results", {})
    assert not findings, "Potential secrets detected:\n" + json.dumps(findings, indent=2)
