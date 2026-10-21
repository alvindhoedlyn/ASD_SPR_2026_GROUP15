"""Verify that Ruff's Bandit-compatible security rules pass."""

import json
import subprocess  # noqa: S404
import sys
from pathlib import Path

import pytest


pytestmark = pytest.mark.pre_commit
ROOT = Path(__file__).resolve().parents[2]


def test_ruff_security_rules_are_configured():
    config = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'select = ["S"]' in config


def test_project_has_no_security_findings():
    result = subprocess.run(  # noqa: S603
        [
            sys.executable,
            "-m",
            "ruff",
            "check",
            "--no-fix",
            "--output-format",
            "json",
            "backend",
            "database",
            "scripts",
            "tests",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode in (0, 1), result.stderr
    findings = json.loads(result.stdout or "[]")
    report = "\n".join(
        f"{item['code']} {item['filename']}:{item['location']['row']} {item['message']}"
        for item in findings
    )
    assert not findings, "Ruff security findings:\n" + report
