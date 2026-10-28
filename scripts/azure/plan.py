#!/usr/bin/env python3
"""Turns docker-compose.yml + docker-compose.cloud.yml into an Azure Container Apps plan.

  docker compose ... config --format json | plan.py plan <domain>      -> JSON plan on stdout
  ... | plan.py lines                                                 -> plan JSON (stdin) as |-separated lines
  plan.py rewrite <stage_dir> <domain>                                -> rewrites URLs in a copy of the code

Why rewrite? The frontends link to each other and call their backends with
http://localhost:<port>, and the nginx configs proxy to compose service names. In Azure every
service has its own address, so the copy of the code that is built into images is rewritten.
The repository source is never changed.
"""
import json
import os
import re
import sys
from pathlib import Path

# compose service -> (container app name, kind). Container app names must be lowercase, <= 32 chars.
APPS = {
    "shared-frontend": ("jb-shared-frontend", "frontend"),
    "shared-backend": ("jb-shared-backend", "backend"),
    "shared-database": ("jb-shared-database", "database"),
    "student-AlvindhoEdlyn-frontend": ("jb-alvindhoedlyn-frontend", "frontend"),
    "student-AlvindhoEdlyn": ("jb-alvindhoedlyn-backend", "backend"),
    "student-AlvindhoEdlyn-database": ("jb-alvindhoedlyn-database", "database"),
    "student-KeyuanGan-frontend": ("jb-keyuangan-frontend", "frontend"),
    "student-KeyuanGan-backend": ("jb-keyuangan-backend", "backend"),
    "student-KeyuanGan-database": ("jb-keyuangan-database", "database"),
    "student-RenzoRobin-frontend": ("jb-renzorobin-frontend", "frontend"),
    "student-RenzoRobin-backend": ("jb-renzorobin-backend", "backend"),
    "student-RenzoRobin-database": ("jb-renzorobin-database", "database"),
    "student-TrongDao": ("jb-trongdao-frontend", "frontend"),
    "student-TrongDao-backend": ("jb-trongdao-backend", "backend"),
    "student-TrongDao-database": ("jb-trongdao-database", "database"),
    "student-YajunNing": ("jb-yajunning-frontend", "frontend"),
    "yajunning-backend-service": ("jb-yajunning-backend", "backend"),
    "yajunning-database-service": ("jb-yajunning-database", "database"),
    "ollama": ("jb-ollama", "llm"),     "rag-server": ("jb-rag-server", "service"),
    "mcp-server": ("jb-mcp-server", "service"),
    "multi-agent-server": ("jb-multi-agent-server", "service"),
}

order = {"llm": 0, "database": 0, "service": 1, "backend": 1, "frontend": 2}
INTERNAL_KINDS = ("database", "llm", "service")   # no public URL

def published_port(service: dict) -> int:
    return int(service["ports"][0]["published"])


def target_port(service: dict) -> int:
    return int(service["ports"][0]["target"])


def internal_urls(text: str, services: dict) -> str:
    """http://<compose-service>:<port> -> http://<container-app> (reachable inside the environment)."""
    for name in services:
        text = re.sub(rf"http://{re.escape(name)}(:\d+)?(?![\w-])", f"http://{APPS[name][0]}", text)
    return text

def build_plan(compose: dict, domain: str) -> list[dict]:
    services = compose["services"]
    plan = []
    for name, service in services.items():
        app, kind = APPS[name]
        build = service["build"]
        context = Path(os.path.relpath(build["context"], os.getcwd())).as_posix()
        env = {key: internal_urls(str(value), services) for key, value in service.get("environment", {}).items()}
        plan.append({
            "service": name,
            "app": app,
            "kind": kind,
            "context": context,
            "dockerfile": build.get("dockerfile", "Dockerfile"),
            "target": build.get("target", ""),
            "port": target_port(service),
            "external": kind not in INTERNAL_KINDS,
            "url": f"https://{app}.{domain}",
            "env": env,
        })
    return sorted(plan, key=lambda item: order[item["kind"]])


def rewrite_tree(stage: Path, domain: str, services: dict) -> int:
    """Rewrite browser links (localhost:<port>) and nginx proxy targets in the staged copy."""
    changed = 0
    for path in stage.rglob("*"):
        if not path.is_file() or "node_modules" in path.parts:
            continue
        in_frontend = "frontend" in path.parts
        if path.suffix in {".html", ".js"} and in_frontend:
            kind = "browser"
        elif path.name == "nginx.conf":
            kind = "nginx"
        else:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        original = text
        if kind == "browser":
            for name, service in services.items():
                app, app_kind = APPS[name]
                if app_kind in INTERNAL_KINDS:   # no public URL for these
                    continue
                if app_kind == "backend":
                    # Backends are internal: a browser link to a backend port goes to that module's frontend,
                    # whose nginx proxies the /api/ calls to the backend.
                    app = app.replace("-backend", "-frontend")
                port = published_port(service)
                text = re.sub(rf"http://localhost:{port}(?!\d)", f"https://{app}.{domain}", text)
            # Trong's frontend builds the backend address from the page host plus :5004; use same-origin paths.
            text = re.sub(
                r"const API_BASE_URL =\s*`\$\{window\.location\.protocol\}//\$\{window\.location\.hostname\}:\d+`;",
                'const API_BASE_URL = "";', text)
        else:
            text = internal_urls(text, services)
            # An internal backend is routed by its Host header, so the proxy must send the backend's own name.
            text = text.replace("proxy_set_header Host $host;", "proxy_set_header Host $proxy_host;")
        if text != original:
            path.write_text(text, encoding="utf-8")
            changed += 1
    return changed


def main() -> int:
    sys.stdout.reconfigure(newline="\n")   # on Windows, "\r\n" would corrupt the last field read by bash
    mode = sys.argv[1]
    if mode == "plan":
        compose = json.load(sys.stdin)
        print(json.dumps(build_plan(compose, sys.argv[2]), indent=2))
        return 0
    if mode == "lines":
        # One line per app: app|kind|port|ingress|context|dockerfile|target|env pairs joined by \x1f
        for item in json.load(sys.stdin):
            ingress = "external" if item["external"] else "internal"
            env = "\x1f".join(f"{key}={value}" for key, value in item["env"].items())
            print("|".join([item["app"], item["kind"], str(item["port"]), ingress,
                            item["context"], item["dockerfile"], item["target"], env]))
        return 0
    if mode == "rewrite":
        compose = json.load(sys.stdin)
        count = rewrite_tree(Path(sys.argv[2]), sys.argv[3], compose["services"])
        print(f"rewrote {count} file(s)")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())