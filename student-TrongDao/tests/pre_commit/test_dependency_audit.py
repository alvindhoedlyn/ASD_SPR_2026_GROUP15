"""Verify that project dependencies have no known vulnerabilities."""

import importlib.util
import json
import subprocess  # noqa: S404
import sys
from pathlib import Path

import pytest


pytestmark = pytest.mark.pre_commit

ROOT = Path(__file__).resolve().parents[2]

REQUIREMENTS_FILES = [
    ROOT / "backend" / "requirements.txt",
    ROOT / "database" / "requirements.txt"
]

PIP_AUDIT_UNAVAILABLE = pytest.mark.skipif(
    importlib.util.find_spec("pip_audit") is None,
    reason="pip-audit is not installed"
)


@pytest.mark.parametrize(
    "requirements_file",
    REQUIREMENTS_FILES,
    ids=lambda path: path.parent.name
)
def test_requirements_file_contains_dependencies(
    requirements_file
):
    assert requirements_file.exists()

    dependencies = [
        line.strip()
        for line in requirements_file.read_text(
            encoding="utf-8"
        ).splitlines()
        if line.strip()
        and not line.strip().startswith("#")
    ]

    assert dependencies, (
        f"{requirements_file} contains no dependencies"
    )


def test_pip_audit_hook_is_configured():
    hook_text = (
        ROOT / ".pre-commit-config.yaml"
    ).read_text(encoding="utf-8")

    assert "id: pip-audit-scan" in hook_text
    assert "test_dependency_audit.py" in hook_text
    assert "--fix" not in hook_text


@PIP_AUDIT_UNAVAILABLE
@pytest.mark.parametrize(
    "requirements_file",
    REQUIREMENTS_FILES,
    ids=lambda path: path.parent.name
)
def test_dependencies_have_no_known_vulnerabilities(
    requirements_file
):
    result = subprocess.run(  # noqa: S603
        [
            sys.executable,
            "-m",
            "pip_audit",
            "-r",
            str(requirements_file),
            "--progress-spinner",
            "off",
            "--format",
            "json"
        ],
        capture_output=True,
        text=True,
        timeout=600,
        check=False
    )

    try:
        audit_report = json.loads(result.stdout)
    except ValueError:
        pytest.fail(
            "pip-audit did not return valid JSON:\n"
            + result.stderr
        )

    vulnerable_dependencies = [
        (
            f"{dependency['name']}=="
            f"{dependency['version']}: "
            + ", ".join(
                vulnerability["id"]
                for vulnerability
                in dependency["vulns"]
            )
        )
        for dependency
        in audit_report.get("dependencies", [])
        if dependency.get("vulns")
    ]

    assert not vulnerable_dependencies, (
        "Vulnerable dependencies found:\n"
        + "\n".join(vulnerable_dependencies)
    )