"""Verify that Ruff reports no security findings."""

import importlib.util
import json
import subprocess  # noqa: S404
import sys
from pathlib import Path

import pytest


pytestmark = pytest.mark.pre_commit

ROOT = Path(__file__).resolve().parents[2]

SCAN_DIRECTORIES = [
    directory
    for directory in (
        "backend",
        "database",
        "agentic_loop",
        "tests"
    )
    if (ROOT / directory).exists()
]

RUFF_UNAVAILABLE = pytest.mark.skipif(
    importlib.util.find_spec("ruff") is None,
    reason="ruff is not installed"
)


def run_ruff(*arguments):
    result = subprocess.run(  # noqa: S603
        [
            sys.executable,
            "-m",
            "ruff",
            "check",
            "--no-fix",
            "--output-format",
            "json",
            *arguments
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False
    )

    assert result.returncode in (0, 1), result.stderr

    return json.loads(result.stdout or "[]")


def test_ruff_security_rules_are_configured():
    config_text = (
        ROOT / "pyproject.toml"
    ).read_text(encoding="utf-8")

    assert 'select = ["S"]' in config_text


def test_ruff_hook_is_configured():
    hook_text = (
        ROOT / ".pre-commit-config.yaml"
    ).read_text(encoding="utf-8")

    assert "id: ruff-scan" in hook_text
    assert "test_ruff_scan.py" in hook_text


@RUFF_UNAVAILABLE
def test_project_has_no_security_findings():
    findings = run_ruff(
        "--select",
        "S",
        *SCAN_DIRECTORIES
    )

    report = "\n".join(
        (
            f"{finding['code']} "
            f"{finding['filename']}:"
            f"{finding['location']['row']} "
            f"{finding['message']}"
        )
        for finding in findings
    )

    assert not findings, (
        "Ruff security findings:\n" + report
    )


@RUFF_UNAVAILABLE
def test_ruff_detects_insecure_example(tmp_path):
    insecure_file = tmp_path / "insecure_example.py"

    insecure_file.write_text(
        "import hashlib\n"
        "hashlib.md5(b'test')\n",
        encoding="utf-8"
    )

    findings = run_ruff(
        "--isolated",
        "--select",
        "S",
        str(insecure_file)
    )

    finding_codes = {
        finding["code"]
        for finding in findings
    }

    assert "S324" in finding_codes