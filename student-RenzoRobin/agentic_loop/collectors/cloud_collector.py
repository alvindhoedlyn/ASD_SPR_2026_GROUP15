"""
Cloud deployment review collector (Azure).

Checks the deployment workflow, scripts and cloud configuration and reads the deployment
results written by the deployment test script (same approach as Lab 11).

Returns (ok, evidence) like the other collectors.
"""
from pathlib import Path

WORKFLOW = ".github/workflows/cloud-deployment.yml"
CLOUD_COMPOSE = "docker-compose.cloud.yml"
SCRIPTS_DIR = "scripts/azure"
DEPLOY_SCRIPT = "deploy-azure.sh"
RESULTS = "reports/cloud/deployment-results.md"
INFO_FLAGS = ("AI_MODE_ENABLED",)  # allowed on: AI runs through the internal Ollama container app
OFF_FLAGS = ("MCP_ENABLED", "RAG_ENABLED", "MULTI_AGENT_ENABLED")  # must stay off in the cloud
TRUE_VALUES = ("true", "1", "yes", "on")
MAX_RESULT_LINES = 40


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""


def _flag_values(text: str, flag: str) -> list[str]:
    values = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(flag):
            values.append(stripped.split(":", 1)[-1].strip().strip('"').strip("'").lower())
    return values


def collect(app_dir: Path, repo_root: Path) -> tuple[bool, str]:
    lines, ok = [], True

    workflow = _read(repo_root / WORKFLOW)
    if not workflow.strip():
        ok = False
        lines.append(f"{WORKFLOW}: missing or empty.")
    else:
        found = [word for word in ("azure/login", "workflow_dispatch", "needs:") if word in workflow]
        lines.append(f"{WORKFLOW}: present, contains {', '.join(found) or 'none of the expected keys'}.")

    scripts_path = repo_root / SCRIPTS_DIR
    scripts = sorted(path.name for path in scripts_path.glob("*.sh")) if scripts_path.exists() else []
    if scripts:
        lines.append(f"{SCRIPTS_DIR}: {len(scripts)} deployment script(s): {', '.join(scripts)}.")
    else:
        ok = False
        lines.append(f"{SCRIPTS_DIR}: no deployment scripts found.")

    deploy = _read(scripts_path / DEPLOY_SCRIPT)
    if deploy.strip():
        has_ingress = "--ingress" in deploy
        has_both = "internal" in deploy + _read(scripts_path / "plan.py") and "external" in deploy + _read(scripts_path / "plan.py")
        lines.append(
            f"{DEPLOY_SCRIPT}: --ingress {'present' if has_ingress else 'MISSING'}, "
            f"internal and external ingress {'both present' if has_both else 'NOT both present'}."
        )
        ok = ok and has_ingress and has_both
    else:
        ok = False
        lines.append(f"{DEPLOY_SCRIPT}: missing or empty.")

    cloud_compose = _read(repo_root / CLOUD_COMPOSE)
    if cloud_compose:
        info = []
        for flag in INFO_FLAGS:
            values = _flag_values(cloud_compose, flag)
            if values:
                info.append(f"{flag}={'true' if any(v in TRUE_VALUES for v in values) else 'false'}")
        on = [flag for flag in OFF_FLAGS if any(v in TRUE_VALUES for v in _flag_values(cloud_compose, flag))]
        off = [flag for flag in OFF_FLAGS if flag not in on]
        lines.append(
            f"{CLOUD_COMPOSE}: flags that must be off and are off: {', '.join(off) or 'none'}"
            + (f"; STILL ENABLED: {', '.join(on)}" if on else "")
            + (f"; information (AI runs on the internal Ollama app): {', '.join(info)}" if info else "")
            + "."
        )
        ok = ok and not on
    else:
        ok = False
        lines.append(f"{CLOUD_COMPOSE}: missing, so the cloud configuration cannot be confirmed.")

    results = _read(repo_root / RESULTS)
    if results.strip():
        shown = results.splitlines()[:MAX_RESULT_LINES]
        lines.append(f"deployment results ({RESULTS}):\n" + "\n".join(shown))
        if "FAIL" in results:
            ok = False
    else:
        ok = False
        lines.append(f"deployment results: {RESULTS} not found (run the deployment test script after deploying).")

    return ok, "\n".join(lines)