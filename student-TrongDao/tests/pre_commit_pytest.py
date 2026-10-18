"""Run a selected pre-commit pytest file from the Student 4 directory."""

import subprocess  # noqa: S404
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TESTS_DIR = ROOT / "tests"


def main(arguments):
    if len(arguments) < 2:
        print(
            "Usage: python tests/pre_commit_pytest.py "
            "<test path> [pytest options]"
        )
        return 2

    target = (ROOT / arguments[1]).resolve()

    if not target.exists():
        print(f"Test path not found: {arguments[1]}")
        return 2

    if TESTS_DIR not in target.parents and target != TESTS_DIR:
        print("Refusing to run anything outside tests.")
        return 2

    command = [
        sys.executable,
        "-m",
        "pytest",
        str(target),
        *arguments[2:]
    ]

    return subprocess.call(  # noqa: S603
        command,
        cwd=ROOT
    )


if __name__ == "__main__":
    sys.exit(main(sys.argv))