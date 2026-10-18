"""Pre-commit: no secrets in the repository (detect-secrets + a pure-Python backstop)."""

import importlib.util
import json
import re
import subprocess  # noqa: S404 - runs detect-secrets only
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.pre_commit

ROOT = Path(__file__).resolve().parents[2]
SOURCE_DIRS = [
    d for d in ("backend", "database", "frontend", "prompts", "agentic_loop") if (ROOT / d).exists()
]
SCAN_DIRS = SOURCE_DIRS + (["tests"] if (ROOT / "tests").exists() else [])
TEXT_SUFFIXES = {
    ".py", ".js", ".html", ".txt", ".yaml", ".yml",
    ".toml", ".json", ".env", ".md", ".cfg", ".ini",
}

# Tool caches (pytest, ruff, python) are generated files, not source.
CACHE_FOLDERS = r"(\.pytest_cache|\.ruff_cache|__pycache__)"
needs_detect_secrets = pytest.mark.skipif(
    importlib.util.find_spec("detect_secrets") is None, reason="detect-secrets is not installed"
)

# Well-known credential shapes, kept here as regexes only.
SECRET_PATTERNS = {
    "AWS access key id": re.compile(r"AKIA[0-9A-Z]{16}"),
    "GitHub token": re.compile(r"gh[pousr]_[A-Za-z0-9]{36,}"),
    "OpenAI-style key": re.compile(r"sk-[A-Za-z0-9]{32,}"),
    "Slack token": re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),
    "Private key block": re.compile(
        r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"
    ),
}


def source_files():
    for directory in SOURCE_DIRS:
        for path in (ROOT / directory).rglob("*"):
            is_text = path.is_file() and path.suffix.lower() in TEXT_SUFFIXES
            if is_text and "node_modules" not in path.parts:
                yield path


def scan(target: Path) -> dict:
    """Run detect-secrets on a folder and return {file: [findings]} (empty when clean).

    detect-secrets silently skips paths outside the current directory, so it is
    run from inside the target folder and told to scan "." instead.
    """
    proc = subprocess.run(  # noqa: S603 - fixed arguments
                [sys.executable, "-m", "detect_secrets", "scan", "--all-files",
         "--exclude-files", CACHE_FOLDERS, "."],
        capture_output=True,
        text=True,
        check=False,
        cwd=target,
    )
    assert proc.returncode == 0, f"detect-secrets failed: {proc.stderr}"
    return json.loads(proc.stdout)["results"]


def test_detect_secrets_hook_is_configured():
    text = (ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    assert "id: detect-secrets-scan" in text
    assert "tests/pre_commit/test_secrets_scan.py" in text


def test_dotenv_file_is_gitignored():
    if not (ROOT / ".env").exists():
        pytest.skip("no .env file in the working tree")
    gitignore = ROOT / ".gitignore"
    assert gitignore.exists(), ".env exists but there is no .gitignore"
    lines = {line.strip() for line in gitignore.read_text(encoding="utf-8").splitlines()}
    assert lines & {".env", ".env*", "*.env"}, ".env is not listed in .gitignore"


def test_no_known_secret_formats_in_source():
    hits = []
    for path in source_files():
        text = path.read_text(encoding="utf-8", errors="ignore")
        for label, pattern in SECRET_PATTERNS.items():
            if pattern.search(text):
                hits.append(f"{label}: {path.relative_to(ROOT)}")
    assert not hits, "Possible secrets found:\n" + "\n".join(hits)


@needs_detect_secrets
def test_detect_secrets_flags_a_planted_secret(tmp_path):
    """Proves the scanner is live: a fake token (assembled at runtime) must be flagged."""
    fake_token = "ghp_" + "R7kP2mXq9LzV4tYw8NbC3dF6hJ1sA5pQeUoX"  # pragma: allowlist secret
    (tmp_path / "leak.py").write_text(f'GITHUB_TOKEN = "{fake_token}"\n', encoding="utf-8")
    assert scan(tmp_path), "detect-secrets did not flag an obvious GitHub token"


@needs_detect_secrets
@pytest.mark.parametrize("directory", SCAN_DIRS)
def test_detect_secrets_finds_nothing_in_project_directory(directory):
    results = scan(ROOT / directory)
    report = "\n".join(
        f"{directory}/{name}:{item['line_number']} {item['type']}"
        for name, items in results.items()
        for item in items
    )
    assert not results, (
        f"detect-secrets flagged {directory}/:\n{report}\n"
        "If a hit is a harmless placeholder, add `# pragma: allowlist secret` to that line."
    )