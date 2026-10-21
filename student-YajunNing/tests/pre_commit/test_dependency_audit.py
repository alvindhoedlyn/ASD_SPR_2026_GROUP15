"""Verify that Student 5 Python dependencies have no known vulnerabilities."""

import json
import subprocess  # noqa: S404
import sys
from pathlib import Path

import pytest


pytestmark = pytest.mark.pre_commit
ROOT = Path(__file__).resolve().parents[2]
REQUIREMENTS = (ROOT / "backend" / "requirements.txt", ROOT / "database" / "requirements.txt")


@pytest.mark.parametrize("requirements_file", REQUIREMENTS, ids=lambda path: path.parent.name)
def test_dependencies_have_no_known_vulnerabilities(requirements_file):
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
            "json",
        ],
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )
    try:
        report = json.loads(result.stdout)
    except ValueError:
        pytest.fail("pip-audit did not return JSON:\n" + result.stderr)

    vulnerable = [
        f"{dependency['name']}=={dependency['version']}: "
        + ", ".join(item["id"] for item in dependency["vulns"])
        for dependency in report.get("dependencies", [])
        if dependency.get("vulns")
    ]
    assert not vulnerable, "Vulnerable dependencies found:\n" + "\n".join(vulnerable)
