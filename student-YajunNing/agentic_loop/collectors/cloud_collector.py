"""Review Azure baseline deployment evidence for the Student 5 service."""

import os
from pathlib import Path

import requests


def read(path):
    return path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""


def collect(app_dir: Path, repo_root: Path):
    workflow = read(repo_root / ".github" / "workflows" / "cloud-deployment.yml")
    cloud_compose = read(repo_root / "docker-compose.cloud.yml")
    scripts = sorted((repo_root / "scripts" / "azure").glob("*.sh"))
    results = read(repo_root / "reports" / "cloud" / "deployment-results.md")
    student_block = cloud_compose.split("yajunning-backend-service:", 1)[-1].split("\n\n", 1)[0]
    flags = ("AI_MODE_ENABLED", "MCP_ENABLED", "RAG_ENABLED", "MULTI_AGENT_ENABLED")

    checks = {
        "cloud-deployment.yml exists": bool(workflow.strip()),
        "Azure login is configured": "azure/login" in workflow,
        "reusable Azure scripts exist": bool(scripts),
        "Student 5 cloud override exists": "yajunning-backend-service:" in cloud_compose,
        "Student 5 AI flags are disabled": all(
            flag in student_block and '"false"' in student_block.split(flag, 1)[1].splitlines()[0]
            for flag in flags
        ),
    }
    lines = [f"{label}: {'PASS' if passed else 'FAIL'}" for label, passed in checks.items()]
    lines.append(f"Azure deployment scripts: {', '.join(path.name for path in scripts) or 'none'}")
    if results.strip():
        lines.append("Deployment result file: present")
        lines.extend(results.splitlines()[:30])
    else:
        lines.append("Deployment result file: missing; run cloud validation after deployment.")

    cloud_url = os.getenv("STUDENT5_CLOUD_URL", "").strip()
    if cloud_url:
        try:
            response = requests.get(cloud_url, timeout=20)
            lines.append(f"Student 5 live cloud check: HTTP {response.status_code}")
            checks["Student 5 live cloud check"] = response.status_code == 200
        except requests.RequestException as exc:
            lines.append(f"Student 5 live cloud check: FAIL - {exc}")
            checks["Student 5 live cloud check"] = False
    else:
        lines.append("Student 5 live cloud check: not run; set STUDENT5_CLOUD_URL after deployment.")

    ok = all(checks.values()) and bool(results.strip())
    lines.append("Final human release decision is required after live cloud validation.")
    return ok, "\n".join(lines)
