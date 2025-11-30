#!/usr/bin/env python
"""Convert recorded trajectories to ADK evaluation fixture format.

Reads the raw trajectory JSON and outputs .test.json files compatible
with ADK's AgentEvaluator.

Usage:
    python scripts/trajectories_to_fixtures.py tests/trajectories/all_trajectories.json
"""

import json
import sys
from pathlib import Path


def trajectory_to_fixture_case(trajectory: dict) -> dict:
    """Convert a single trajectory to an ADK test case.

    Args:
        trajectory: Raw trajectory dict with prompt, tool_calls, final_response

    Returns:
        ADK test case dict
    """
    # Convert tool calls to expected_tool_use format
    expected_tool_use = []
    for tc in trajectory.get("tool_calls", []):
        expected_tool_use.append({
            "tool_name": tc["name"],
            "tool_input": tc["input"],
        })

    return {
        "query": trajectory["prompt"],
        "expected_tool_use": expected_tool_use,
        "reference": trajectory.get("final_response", "")[:200],  # Truncate for matching
    }


def create_fixture_file(name: str, description: str, cases: list[dict]) -> dict:
    """Create a complete fixture file structure.

    Args:
        name: Test set name (e.g., "intent_classification")
        description: Description of what the test verifies
        cases: List of test cases

    Returns:
        Complete fixture dict
    """
    return {
        "name": name,
        "description": description,
        "data": cases,
    }


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/trajectories_to_fixtures.py <trajectories.json>")
        sys.exit(1)

    input_file = Path(sys.argv[1])
    if not input_file.exists():
        print(f"File not found: {input_file}")
        sys.exit(1)

    # Load trajectories
    with open(input_file) as f:
        trajectories = json.load(f)

    print(f"Loaded {len(trajectories)} trajectories")

    # Group by category if present
    categorized: dict[str, list] = {}
    for t in trajectories:
        # Determine category from the trajectory
        tool_names = [tc["name"] for tc in t.get("tool_calls", [])]

        if "create_waterfall_page" in tool_names:
            if "DUPLICATE_FOUND" in str(t.get("tool_calls", [])):
                category = "duplicate_detection"
            elif "RESEARCH_FAILED" in str(t.get("tool_calls", [])):
                category = "fake_waterfall_rejection"
            else:
                category = "content_creation"
        elif "list_pages" in tool_names or "search_pages" in tool_names:
            category = "list_and_search"
        elif "move_page" in tool_names or "publish_page" in tool_names:
            category = "page_management"
        elif len(tool_names) == 1 and tool_names[0] == "classify_intent":
            # Only router called - conversational or needs follow-up
            category = "conversational"
        else:
            category = "other"

        if category not in categorized:
            categorized[category] = []
        categorized[category].append(trajectory_to_fixture_case(t))

    # Output fixtures
    fixtures_dir = Path("tests/fixtures")
    fixtures_dir.mkdir(exist_ok=True)

    for category, cases in categorized.items():
        fixture = create_fixture_file(
            name=category,
            description=f"Tests for {category.replace('_', ' ')} scenarios",
            cases=cases,
        )

        output_file = fixtures_dir / f"{category}.test.json"
        with open(output_file, "w") as f:
            json.dump(fixture, f, indent=2)

        print(f"Created {output_file} with {len(cases)} test cases")

    # Also create a combined "all" fixture
    all_cases = []
    for t in trajectories:
        all_cases.append(trajectory_to_fixture_case(t))

    all_fixture = create_fixture_file(
        name="all_trajectories",
        description="All recorded test trajectories",
        cases=all_cases,
    )

    all_file = fixtures_dir / "all_recorded.test.json"
    with open(all_file, "w") as f:
        json.dump(all_fixture, f, indent=2)

    print(f"\nCreated combined fixture: {all_file}")
    print(f"Total test cases: {len(all_cases)}")


if __name__ == "__main__":
    main()
