"""Run one trusted Student 5 pytest target from a pre-commit hook."""

import subprocess  # noqa: S404
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TESTS_DIRECTORY = ROOT / "tests"


def main(arguments):
    if len(arguments) < 2:
        print("Usage: pre_commit_pytest.py <test path> [pytest options]")
        return 2

    target = (ROOT / arguments[1]).resolve()
    if not target.exists():
        print(f"Test path not found: {arguments[1]}")
        return 2
    if TESTS_DIRECTORY not in target.parents and target != TESTS_DIRECTORY:
        print("Refusing to run anything outside the Student 5 tests directory.")
        return 2

    command = [sys.executable, "-m", "pytest", str(target), *arguments[2:]]
    return subprocess.call(command, cwd=ROOT)  # noqa: S603


if __name__ == "__main__":
    sys.exit(main(sys.argv))
