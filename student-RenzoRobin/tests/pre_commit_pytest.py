"""Hook launcher: runs one pytest file (plus any extra pytest flags) for pre-commit.

Usage (from the repo root):
    python student-RenzoRobin/tests/pre_commit_pytest.py tests/pre_commit/test_ruff_scan.py -v
"""

import subprocess  # noqa: S404 - launcher only runs pytest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TESTS_DIR = ROOT / "tests"


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: python tests/pre_commit_pytest.py <test file or folder> [pytest args...]")
        return 2

    target = (ROOT / argv[1]).resolve()
    if not target.exists():
        print(f"Test path not found: {argv[1]}")
        return 2
    if TESTS_DIR not in target.parents and target != TESTS_DIR:
        print("Refusing to run anything outside the tests/ folder.")
        return 2

    cmd = [sys.executable, "-m", "pytest", str(target), *argv[2:]]
    return subprocess.call(cmd, cwd=ROOT)  # noqa: S603 - trusted, repo-controlled arguments


if __name__ == "__main__":
    sys.exit(main(sys.argv))