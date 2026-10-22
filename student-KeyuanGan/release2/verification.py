import subprocess
import sys


def run_verification(repo_root):
    commands = {
        "unit_tests": [
            sys.executable, "-m", "unittest",
            "discover",
            "-s", "student-KeyuanGan/tests",
            "-p", "test_*.py",
            "-v",
        ],
        "ruff": [
            sys.executable, "-m", "ruff", "check",
            "student-KeyuanGan",
            "--select", "E4,E7,E9,F,S",
        ],
        "pip_audit": [
            sys.executable, "-m", "pip_audit",
            "-r", "student-KeyuanGan/backend/requirements.txt",
            "-r", "student-KeyuanGan/database/requirements.txt",
        ],
    }

    results = {}

    for name, command in commands.items():
        print(f"\n=== Running {name} ===", flush=True)

        try:
            result = subprocess.run(  # noqa: S603 - fixed command list, no shell
                command,
                cwd=repo_root,
                capture_output=True,
                text=True,
                timeout=180,
                check=False,
            )

            results[name] = {
                "passed": result.returncode == 0,
                "exit_code": result.returncode,
                "output": (result.stdout + result.stderr)[-6000:],
            }

        except (OSError, subprocess.TimeoutExpired) as error:
            results[name] = {
                "passed": False,
                "exit_code": None,
                "output": str(error),
            }

        print(
            f"{name}: "
            f"{'PASS' if results[name]['passed'] else 'FAIL'}"
        )

    return results
