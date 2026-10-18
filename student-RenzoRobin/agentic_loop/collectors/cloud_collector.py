"""
Cloud deployment review collector (Azure).

Checks the deployment workflow, scripts and cloud configuration, reads the deployment
results written by the deployment test script, and (optionally) probes the deployed
frontend when CLOUD_URL is set.

Returns (ok, evidence) like the other collectors.
"""
import os
from pathlib import Path

import requests

WORKFLOW = ".github/workflows/cloud-deployment.yml"
CLOUD_COMPOSE = "docker-compose.cloud.yml"
SCRIPTS_DIR = "scripts/azure"
RESULTS = "reports/cloud/deployment-results.md"
AI_FLAGS = ("AI_MODE_ENABLED", "MCP_ENABLED", "RAG_ENABLED", "MULTI_AGENT_ENABLED")
MAX_RESULT_LINES = 40


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""


def collect(app_dir: Path, repo_root: Path) -> tuple[bool, str]:
    lines, ok = [], True

    workflow = _read(repo_root / WORKFLOW)
    if not workflow.strip():
        ok = False
        lines.append(f"{WORKFLOW}: missing or empty.")
    else:
        found = [word for word in ("azure/login", "workflow_dispatch", "needs:") if word in workflow]
        lines.append(f"{WORKFLOW}: present, contains {', '.join(found) or 'none of the expected keys'}.")

    scripts = sorted(path.name for path in (repo_root / SCRIPTS_DIR).glob("*.sh")) if (repo_root / SCRIPTS_DIR).exists() else []
    if scripts:
        lines.append(f"{SCRIPTS_DIR}: {len(scripts)} deployment script(s): {', '.join(scripts)}.")
    else:
        ok = False
        lines.append(f"{SCRIPTS_DIR}: no deployment scripts found.")

    cloud_compose = _read(repo_root / CLOUD_COMPOSE)
    if cloud_compose:
        enabled = [
            flag for flag in AI_FLAGS
            if any(flag in line and "true" in line.lower() for line in cloud_compose.splitlines())
        ]
        listed = [flag for flag in AI_FLAGS if flag in cloud_compose]
        lines.append(
            f"{CLOUD_COMPOSE}: AI flags set to false: {', '.join(f for f in listed if f not in enabled) or 'none'}"
            + (f"; STILL ENABLED: {', '.join(enabled)}" if enabled else "")
            + "."
        )
        ok = ok and not enabled
    else:
        ok = False
        lines.append(f"{CLOUD_COMPOSE}: missing, so the AI-disabled baseline cannot be confirmed.")

    results = _read(repo_root / RESULTS)
    if results.strip():
        shown = results.splitlines()[:MAX_RESULT_LINES]
        lines.append(f"deployment results ({RESULTS}):\n" + "\n".join(shown))
        if "FAIL" in results:
            ok = False
    else:
        lines.append(f"deployment results: {RESULTS} not found (run the deployment test script after deploying).")

    cloud_url = os.environ.get("CLOUD_URL", "").strip()
    if cloud_url:
        try:
            status = requests.get(cloud_url, timeout=20).status_code
            lines.append(f"live check {cloud_url}: HTTP {status}.")
            ok = ok and status == 200
        except requests.exceptions.RequestException as exc:
            ok = False
            lines.append(f"live check {cloud_url}: request failed - {exc}")
    else:
        lines.append("live check: CLOUD_URL not set, so the deployed frontend was not probed.")

    return ok, "\n".join(lines)