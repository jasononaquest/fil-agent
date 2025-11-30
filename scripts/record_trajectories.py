#!/usr/bin/env python
"""Record actual agent trajectories for evaluation fixtures.

This script runs test prompts against the agent and captures the complete
tool call trajectory. Output can be used to:
1. Create accurate evaluation fixtures
2. Analyze agent behavior for efficiency
3. Debug unexpected tool sequences

Usage:
    # Record all test prompts
    python scripts/record_trajectories.py

    # Record specific prompt
    python scripts/record_trajectories.py "Create a page for Multnomah Falls"

    # Output as ADK fixture format
    python scripts/record_trajectories.py --format fixture

    # Verbose output with full tool inputs/outputs
    python scripts/record_trajectories.py --verbose
"""

import argparse
import asyncio
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from falls_cms_agent.agent import root_agent


@dataclass
class ToolCall:
    """Captured tool call."""

    name: str
    input: dict[str, Any]
    output: Any = None
    duration_ms: float = 0


@dataclass
class Trajectory:
    """Complete trajectory for a single prompt."""

    prompt: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    final_response: str = ""
    total_duration_ms: float = 0
    timestamp: str = ""


# Test prompts covering all agent capabilities
TEST_PROMPTS = [
    # Intent Classification
    {
        "prompt": "Create a page for La Paz Waterfall Gardens in Costa Rica",
        "category": "create_page_success",
        "expected_intent": "CREATE_PAGE",
        "expected_outcome": "success",
    },
    {
        "prompt": "Create a page for Multnomah Falls in Oregon",
        "category": "create_page_duplicate",
        "expected_intent": "CREATE_PAGE",
        "expected_outcome": "duplicate",
    },
    {
        "prompt": "What pages are in the Oregon category?",
        "category": "list_pages",
        "expected_intent": "LIST_PAGES",
    },
    {
        "prompt": "Find pages about waterfalls near Portland",
        "category": "search",
        "expected_intent": "SEARCH_CMS",
    },
    {
        "prompt": "Move Multnomah Falls to the Columbia River Gorge category",
        "category": "move_page",
        "expected_intent": "MOVE_PAGE",
    },
    {
        "prompt": "Publish the Cherry Creek Falls page",
        "category": "publish",
        "expected_intent": "PUBLISH_PAGE",
    },
    {
        "prompt": "Add hiking tips to the Multnomah Falls page",
        "category": "update_content",
        "expected_intent": "UPDATE_CONTENT",
    },
    # Edge cases
    {
        "prompt": "Create a page for Rainbow Unicorn Falls",
        "category": "fake_waterfall",
        "expected_outcome": "research_failed",
    },
    {
        "prompt": "Publish the Imaginary Falls page",
        "category": "error_handling",
        "expected_outcome": "page_not_found",
    },
    # Conversations
    {
        "prompt": "Hello, what can you do?",
        "category": "greeting",
        "expected_intent": "CONVERSATION",
    },
]


async def record_trajectory(prompt: str, verbose: bool = False) -> Trajectory:
    """Run a prompt through the agent and record the trajectory.

    Args:
        prompt: The user prompt to send
        verbose: Whether to print detailed output

    Returns:
        Trajectory with all tool calls and final response
    """
    trajectory = Trajectory(
        prompt=prompt,
        timestamp=datetime.now().isoformat(),
    )

    # Set up session service and create session
    app_name = "falls_cms_agent"
    user_id = "record_user"
    session_id = f"record_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    session_service = InMemorySessionService()
    # Pre-create the session to avoid "session not found" errors
    await session_service.create_session(
        app_name=app_name,
        user_id=user_id,
        session_id=session_id,
    )

    runner = Runner(
        agent=root_agent,
        app_name=app_name,
        session_service=session_service,
    )

    content = types.Content(
        role="user",
        parts=[types.Part(text=prompt)],
    )

    start_time = datetime.now()
    current_tool: ToolCall | None = None

    if verbose:
        print(f"\n{'=' * 60}")
        print(f"PROMPT: {prompt}")
        print("=" * 60)

    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=content,
    ):
        # Capture tool calls
        if hasattr(event, "content") and event.content:
            for part in event.content.parts if hasattr(event.content, "parts") else []:
                # Tool call start
                if hasattr(part, "function_call") and part.function_call:
                    fc = part.function_call
                    current_tool = ToolCall(
                        name=fc.name,
                        input=dict(fc.args) if fc.args else {},
                    )
                    if verbose:
                        print(f"\n→ TOOL: {fc.name}")
                        print(f"  INPUT: {json.dumps(current_tool.input, indent=2)}")

                # Tool response
                if hasattr(part, "function_response") and part.function_response:
                    fr = part.function_response
                    if current_tool and current_tool.name == fr.name:
                        current_tool.output = fr.response
                        trajectory.tool_calls.append(current_tool)
                        if verbose:
                            output_str = json.dumps(fr.response, indent=2, default=str)
                            if len(output_str) > 500:
                                output_str = output_str[:500] + "..."
                            print(f"  OUTPUT: {output_str}")
                        current_tool = None

                # Text response
                if hasattr(part, "text") and part.text:
                    trajectory.final_response += part.text

    trajectory.total_duration_ms = (datetime.now() - start_time).total_seconds() * 1000

    if verbose:
        print(f"\n{'─' * 60}")
        print(f"RESPONSE: {trajectory.final_response[:500]}...")
        print(f"DURATION: {trajectory.total_duration_ms:.0f}ms")
        print(f"TOOL CALLS: {len(trajectory.tool_calls)}")

    return trajectory


def trajectory_to_fixture(trajectory: Trajectory, test_name: str) -> dict:
    """Convert a trajectory to ADK evaluation fixture format.

    Args:
        trajectory: The recorded trajectory
        test_name: Name for this test case

    Returns:
        Dict in ADK .test.json format
    """
    return {
        "query": trajectory.prompt,
        "expected_tool_use": [
            {
                "tool_name": tc.name,
                "tool_input": tc.input,
            }
            for tc in trajectory.tool_calls
        ],
        "reference": trajectory.final_response[:200],  # Truncate for matching
    }


def analyze_trajectory(trajectory: Trajectory) -> dict:
    """Analyze a trajectory for efficiency and correctness.

    Args:
        trajectory: The recorded trajectory

    Returns:
        Analysis dict with metrics and observations
    """
    tool_names = [tc.name for tc in trajectory.tool_calls]

    analysis = {
        "prompt": trajectory.prompt,
        "total_tools": len(trajectory.tool_calls),
        "unique_tools": len(set(tool_names)),
        "tool_sequence": tool_names,
        "duration_ms": trajectory.total_duration_ms,
        "observations": [],
    }

    # Check for classify_intent first (expected pattern)
    if tool_names and tool_names[0] == "classify_intent":
        analysis["observations"].append("✓ Router called first (correct)")
    elif tool_names:
        analysis["observations"].append("⚠ Router NOT called first")

    # Check for duplicate tools
    for i, name in enumerate(tool_names[1:], 1):
        if name == tool_names[i - 1]:
            analysis["observations"].append(f"⚠ Duplicate consecutive call: {name}")

    # Check for MCP efficiency
    mcp_calls = [n for n in tool_names if n not in ["classify_intent"]]
    if len(mcp_calls) > 5:
        analysis["observations"].append(f"⚠ High MCP call count: {len(mcp_calls)}")

    # Check response
    if not trajectory.final_response:
        analysis["observations"].append("⚠ No final response")
    elif "SUCCESS" in trajectory.final_response:
        analysis["observations"].append("✓ Operation successful")
    elif "FAILED" in trajectory.final_response or "ERROR" in trajectory.final_response:
        analysis["observations"].append("✓ Error properly reported")

    return analysis


async def main():
    parser = argparse.ArgumentParser(description="Record agent trajectories")
    parser.add_argument(
        "prompt",
        nargs="?",
        help="Specific prompt to record (runs all if not specified)",
    )
    parser.add_argument(
        "--format",
        choices=["analysis", "fixture", "raw"],
        default="analysis",
        help="Output format",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed tool calls")
    parser.add_argument("--output", "-o", help="Output file (prints to stdout if not specified)")
    parser.add_argument(
        "--category",
        "-c",
        help="Only run prompts from this category",
    )

    args = parser.parse_args()

    # Determine which prompts to run
    if args.prompt:
        prompts = [{"prompt": args.prompt, "category": "custom"}]
    elif args.category:
        prompts = [p for p in TEST_PROMPTS if p.get("category") == args.category]
    else:
        prompts = TEST_PROMPTS

    if not prompts:
        print(f"No prompts found for category: {args.category}")
        return

    print(f"Recording {len(prompts)} trajectories...")

    results = []
    for prompt_info in prompts:
        prompt = prompt_info["prompt"]
        print(f"\n[{len(results) + 1}/{len(prompts)}] {prompt[:50]}...")

        try:
            trajectory = await record_trajectory(prompt, verbose=args.verbose)

            if args.format == "fixture":
                result = trajectory_to_fixture(
                    trajectory, f"test_{prompt_info.get('category', 'custom')}"
                )
            elif args.format == "raw":
                result = {
                    "prompt": trajectory.prompt,
                    "timestamp": trajectory.timestamp,
                    "tool_calls": [
                        {
                            "name": tc.name,
                            "input": tc.input,
                            "output": tc.output,
                        }
                        for tc in trajectory.tool_calls
                    ],
                    "final_response": trajectory.final_response,
                    "duration_ms": trajectory.total_duration_ms,
                }
            else:  # analysis
                result = analyze_trajectory(trajectory)

            results.append(result)

        except Exception as e:
            print(f"  ERROR: {e}")
            results.append({"prompt": prompt, "error": str(e)})

    # Output results
    output = json.dumps(results, indent=2, default=str)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output)
        print(f"\nResults saved to: {args.output}")
    else:
        print("\n" + "=" * 60)
        print("RESULTS")
        print("=" * 60)
        print(output)

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    successful = [r for r in results if "error" not in r]
    print(f"Recorded: {len(successful)}/{len(prompts)} trajectories")

    if args.format == "analysis":
        for r in successful:
            print(f"\n{r['prompt'][:40]}...")
            print(f"  Tools: {r['tool_sequence']}")
            for obs in r.get("observations", []):
                print(f"  {obs}")


if __name__ == "__main__":
    asyncio.run(main())
