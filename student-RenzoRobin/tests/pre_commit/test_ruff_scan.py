"""Pre-commit: ruff must run security (flake8-bandit `S`) rules only, and find nothing."""

import importlib.util
import json
import subprocess  # noqa: S404 - runs ruff only
import sys
from pathlib import Path

import pytest

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib

pytestmark = pytest.mark.pre_commit

ROOT = Path(__file__).resolve().parents[2]
SCAN_DIRS = [d for d in ("backend", "database", "agentic_loop", "tests") if (ROOT / d).exists()]

needs_ruff = pytest.mark.skipif(
    importlib.util.find_spec("ruff") is None, reason="ruff is not installed"
)


def run_ruff(*args: str) -> list[dict]:
    proc = subprocess.run(  # noqa: S603 - fixed arguments
        [sys.executable, "-m", "ruff", "check", "--no-fix", "--output-format", "json", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode in (0, 1), f"ruff crashed: {proc.stderr}"
    return json.loads(proc.stdout or "[]")


def test_ruff_config_selects_only_bandit_rules():
    config = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    lint = config["tool"]["ruff"]["lint"]
    assert lint["select"] == ["S"]
    assert not lint.get("extend-select")


def test_ruff_hook_is_configured():
    text = (ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    assert "id: ruff-scan" in text
    assert "tests/pre_commit/test_ruff_scan.py" in text


@needs_ruff
def test_no_security_findings_in_project_code():
    findings = run_ruff("--select", "S", *SCAN_DIRS)
    report = "\n".join(
        f"{f['code']} {f['filename']}:{f['location']['row']} {f['message']}" for f in findings
    )
    assert not findings, f"Security findings:\n{report}"


@needs_ruff
def test_ruff_actually_flags_known_bad_code(tmp_path):
    """Sanity check: proves the scan is not silently passing on everything."""
    bad = tmp_path / "bad.py"
    bad.write_text(
        "import hashlib\nimport subprocess\n"
        "hashlib.md5(b'x')\n"
        "subprocess.call('ls', shell=True)\n",
        encoding="utf-8",
    )
    findings = run_ruff("--isolated", "--select", "S", str(bad))
    codes = {f["code"] for f in findings}
    assert "S324" in codes  # insecure hash function
    assert codes & {"S602", "S604"}  # shell=True