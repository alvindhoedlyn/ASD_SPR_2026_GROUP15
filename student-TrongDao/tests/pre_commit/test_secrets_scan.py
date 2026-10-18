"""Verify that project files do not contain committed secrets."""

import importlib.util
import json
import re
import subprocess  # noqa: S404
import sys
from pathlib import Path

import pytest


pytestmark = pytest.mark.pre_commit

ROOT = Path(__file__).resolve().parents[2]

SOURCE_DIRECTORIES = [
    directory
    for directory in (
        "backend",
        "database",
        "frontend",
        "agentic_loop",
        "tests"
    )
    if (ROOT / directory).exists()
]

TEXT_SUFFIXES = {
    ".py",
    ".js",
    ".html",
    ".css",
    ".txt",
    ".yaml",
    ".yml",
    ".toml",
    ".json",
    ".env",
    ".md"
}

CACHE_FOLDERS = (
    r"(\.pytest_cache|\.ruff_cache|__pycache__)"
)

DETECT_SECRETS_UNAVAILABLE = pytest.mark.skipif(
    importlib.util.find_spec("detect_secrets") is None,
    reason="detect-secrets is not installed"
)

SECRET_PATTERNS = {
    "AWS access key": re.compile(
        r"AKIA[0-9A-Z]{16}"
    ),
    "GitHub token": re.compile(
        r"gh[pousr]_[A-Za-z0-9]{36,}"
    ),
    "OpenAI-style key": re.compile(
        r"sk-[A-Za-z0-9]{32,}"
    ),
    "private key": re.compile(
        (
            r"-----BEGIN "
            r"(?:RSA |EC |OPENSSH |DSA )?"
            r"PRIVATE KEY-----"
        )
    )
}


def source_files():
    for directory in SOURCE_DIRECTORIES:
        for path in (ROOT / directory).rglob("*"):
            is_text_file = (
                path.is_file()
                and path.suffix.lower() in TEXT_SUFFIXES
            )

            if (
                is_text_file
                and "node_modules" not in path.parts
                and "__pycache__" not in path.parts
            ):
                yield path


def run_detect_secrets(target):
    result = subprocess.run(  # noqa: S603
        [
            sys.executable,
            "-m",
            "detect_secrets",
            "scan",
            "--all-files",
            "--exclude-files",
            CACHE_FOLDERS,
            "."
        ],
        cwd=target,
        capture_output=True,
        text=True,
        check=False
    )

    assert result.returncode == 0, result.stderr

    return json.loads(result.stdout)["results"]


def test_detect_secrets_hook_is_configured():
    hook_text = (
        ROOT / ".pre-commit-config.yaml"
    ).read_text(encoding="utf-8")

    assert "id: detect-secrets-scan" in hook_text
    assert "test_secrets_scan.py" in hook_text


def test_no_known_secret_formats_in_source():
    findings = []

    for path in source_files():
        contents = path.read_text(
            encoding="utf-8",
            errors="ignore"
        )

        for label, pattern in SECRET_PATTERNS.items():
            if pattern.search(contents):
                relative_path = path.relative_to(ROOT)
                findings.append(
                    f"{label}: {relative_path}"
                )

    assert not findings, (
        "Possible secrets found:\n"
        + "\n".join(findings)
    )


@DETECT_SECRETS_UNAVAILABLE
def test_scanner_detects_planted_secret(tmp_path):
    fake_token = (
    "ghp_"
    + "R7kP2mXq9LzV4tYw8NbC3dF6hJ1sA5pQeUoX"  # pragma: allowlist secret
    )

    test_file = tmp_path / "secret_example.py"
    test_file.write_text(
        f'GITHUB_TOKEN = "{fake_token}"\n',
        encoding="utf-8"
    )

    assert run_detect_secrets(tmp_path)


@DETECT_SECRETS_UNAVAILABLE
@pytest.mark.parametrize(
    "directory",
    SOURCE_DIRECTORIES
)
def test_no_secrets_in_project_directory(directory):
    results = run_detect_secrets(
        ROOT / directory
    )

    report = "\n".join(
        (
            f"{directory}/{filename}:"
            f"{finding['line_number']} "
            f"{finding['type']}"
        )
        for filename, file_findings in results.items()
        for finding in file_findings
    )

    assert not results, (
        f"Secrets detected in {directory}:\n"
        + report
    )
