"""
Release 1 Shared Agentic Loop Validation

Adds two local, non-containerised validation modes to the shared agentic loop:

1. MCP Validation Mode
2. RAG Validation Mode

The validator runs directly on the host machine and connects to:
- Shared MCP Server: http://localhost:5200/mcp
- Shared RAG Server: http://localhost:5100

Usage:
    python shared/agentic_loop/release1_validation.py --mode mcp
    python shared/agentic_loop/release1_validation.py --mode rag
    python shared/agentic_loop/release1_validation.py --mode all
"""

import argparse
import asyncio
import json
import sys
from typing import Any
from urllib import error, request

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


MCP_SERVER_URL = "http://localhost:5200/mcp"
RAG_SERVER_URL = "http://localhost:5100"


def print_stage(mode: str, stage: str, message: str) -> None:
    """Print a consistent shared agentic-loop validation trace."""
    print(f"[{mode}][{stage}] {message}")


def print_json(data: Any) -> None:
    """Pretty-print validation evidence."""
    print(json.dumps(data, indent=2, ensure_ascii=False))


def extract_mcp_content(result: Any) -> list[Any]:
    """Extract readable content from an MCP CallToolResult."""
    extracted: list[Any] = []

    for block in getattr(result, "content", []) or []:
        text = getattr(block, "text", None)

        if text is None:
            extracted.append(str(block))
            continue

        try:
            extracted.append(json.loads(text))
        except (json.JSONDecodeError, TypeError):
            extracted.append(text)

    return extracted


async def run_mcp_validation() -> bool:
    """
    MCP Validation Mode.

    Validates that the shared local MCP server:
    - is reachable;
    - exposes registered tools;
    - exposes budget_summary;
    - accepts a valid tool request;
    - returns a structured result.
    """
    mode = "MCP VALIDATION"

    print()
    print("=" * 70)
    print("SHARED AGENTIC LOOP - MCP VALIDATION MODE")
    print("=" * 70)

    print_stage(mode, "START", "Starting local MCP validation")
    print_stage(mode, "PLAN", f"Connect to shared MCP server at {MCP_SERVER_URL}")

    try:
        print_stage(mode, "ACT", "Opening MCP Streamable HTTP session")

        async with streamable_http_client(MCP_SERVER_URL) as (
            read_stream,
            write_stream,
            _,
        ):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()

                print_stage(
                    mode,
                    "OBSERVE",
                    "Connected to shared local MCP server successfully",
                )

                print_stage(mode, "ACT", "Requesting registered MCP tools")
                tools_result = await session.list_tools()

                tool_names = [tool.name for tool in tools_result.tools]

                print_stage(
                    mode,
                    "OBSERVE",
                    f"Registered tools: {', '.join(tool_names)}",
                )

                if "budget_summary" not in tool_names:
                    print_stage(
                        mode,
                        "VALIDATE",
                        "FAILED - required budget_summary tool is not registered",
                    )
                    return False

                print_stage(
                    mode,
                    "ACT",
                    "Calling registered tool: budget_summary",
                )

                result = await session.call_tool(
                    "budget_summary",
                    arguments={},
                )

                if getattr(result, "isError", False):
                    print_stage(
                        mode,
                        "VALIDATE",
                        "FAILED - MCP tool returned an error",
                    )
                    return False

                structured_content = getattr(result, "structuredContent", None)
                readable_content = extract_mcp_content(result)

                evidence = {
                    "server": MCP_SERVER_URL,
                    "registered_tools": tool_names,
                    "tool_called": "budget_summary",
                    "structured_content": structured_content,
                    "content": readable_content,
                }

                print_stage(
                    mode,
                    "OBSERVE",
                    "Received MCP tool result",
                )
                print_json(evidence)

                if not structured_content and not readable_content:
                    print_stage(
                        mode,
                        "VALIDATE",
                        "FAILED - MCP returned no usable result",
                    )
                    return False

                print_stage(
                    mode,
                    "VALIDATE",
                    "PASSED - shared MCP server returned a valid tool result",
                )
                print_stage(mode, "DONE", "MCP validation complete")
                return True

    except Exception as exc:
        print_stage(
            mode,
            "ERROR",
            f"MCP validation failed: {exc}",
        )
        return False


def post_json(url: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Send a JSON POST request using the Python standard library."""
    body = json.dumps(payload).encode("utf-8")

    req = request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with request.urlopen(req, timeout=15) as response:
            response_body = response.read().decode("utf-8")
            return json.loads(response_body)

    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"HTTP {exc.code} returned by RAG server: {body}"
        ) from exc

    except error.URLError as exc:
        raise RuntimeError(
            f"Could not connect to RAG server: {exc.reason}"
        ) from exc


def run_rag_validation() -> bool:
    """
    RAG Validation Mode.

    Validates that the shared local RAG server:
    - is reachable;
    - accepts a project-knowledge query;
    - returns a grounded answer;
    - returns source citation information;
    - returns a confidence category.
    """
    mode = "RAG VALIDATION"

    print()
    print("=" * 70)
    print("SHARED AGENTIC LOOP - RAG VALIDATION MODE")
    print("=" * 70)

    query = "How is remaining budget calculated in the Budget Tracker?"

    print_stage(mode, "START", "Starting local RAG validation")
    print_stage(mode, "PLAN", f"Query shared RAG server at {RAG_SERVER_URL}")
    print_stage(mode, "ACT", f"Submitting grounded query: {query}")

    try:
        result = post_json(
            f"{RAG_SERVER_URL}/answer",
            {"query": query, "k": 5, "caller": "agentic-loop-validation"},
        )

        print_stage(mode, "OBSERVE", "Received RAG response")
        print_json(result)

        answer = result.get("answer")
        confidence = result.get("confidence_category")
        sources = result.get("citations")

        if not isinstance(answer, str) or not answer.strip():
            print_stage(
                mode,
                "VALIDATE",
                "FAILED - RAG response does not contain a grounded answer",
            )
            return False

        if not confidence:
            print_stage(
                mode,
                "VALIDATE",
                "FAILED - RAG response does not contain a confidence category",
            )
            return False

        if str(confidence).lower() == "insufficient":
            print_stage(
                mode,
                "VALIDATE",
                "FAILED - approved validation query returned insufficient context",
            )
            return False

        if not isinstance(sources, list) or not sources:
            print_stage(
                mode,
                "VALIDATE",
                "FAILED - RAG response does not contain source citations",
            )
            return False

        print_stage(
            mode,
            "VALIDATE",
            f"Grounded answer validated with confidence '{confidence}'",
        )

        print_stage(
            mode,
            "VALIDATE",
            "PASSED - answer, source citation and confidence category are present",
        )

        print_stage(mode, "DONE", "RAG validation complete")
        return True

    except Exception as exc:
        print_stage(
            mode,
            "ERROR",
            f"RAG validation failed: {exc}",
        )
        return False


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Release 1 shared local MCP/RAG agentic-loop validator"
    )

    parser.add_argument(
        "--mode",
        choices=("mcp", "rag", "all"),
        required=True,
        help="Validation mode to execute",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_arguments()

    print("=" * 70)
    print("JOURNEYBUDDY RELEASE 1 - SHARED AGENTIC LOOP")
    print("Local / Non-containerised Validation")
    print("=" * 70)

    results: dict[str, bool] = {}

    if args.mode in ("mcp", "all"):
        results["mcp"] = asyncio.run(run_mcp_validation())

    if args.mode in ("rag", "all"):
        results["rag"] = run_rag_validation()

    print()
    print("=" * 70)
    print("VALIDATION SUMMARY")
    print("=" * 70)

    for mode_name, passed in results.items():
        status = "PASSED" if passed else "FAILED"
        print(f"{mode_name.upper()}: {status}")

    overall_passed = bool(results) and all(results.values())

    print("-" * 70)
    print(
        "OVERALL:",
        "PASSED" if overall_passed else "FAILED",
    )

    sys.exit(0 if overall_passed else 1)


if __name__ == "__main__":
    main()
