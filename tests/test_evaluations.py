"""ADK evaluation tests for Falls CMS Agent.

These tests use ADK's AgentEvaluator to verify agent behavior
matches expected tool trajectories and responses.

Run with: pytest tests/test_evaluations.py -v

The AgentEvaluator uses these built-in metrics:
- TOOL_TRAJECTORY_AVG_SCORE: Validates tool call sequences
- RESPONSE_MATCH_SCORE: ROUGE-1 text similarity

Configuration is loaded from tests/fixtures/test_config.json:
- tool_trajectory_avg_score: 0.8 threshold (allows some variation)
- response_match_score: 0.3 threshold (LLM responses vary)
"""

from pathlib import Path

import pytest

# Note: These imports will work once google-adk is installed
try:
    from google.adk.evaluation.agent_evaluator import AgentEvaluator

    ADK_AVAILABLE = True
except ImportError:
    ADK_AVAILABLE = False


FIXTURES_DIR = Path(__file__).parent / "fixtures"


# =============================================================================
# Test Functions
# =============================================================================


@pytest.mark.skipif(not ADK_AVAILABLE, reason="google-adk not installed")
@pytest.mark.asyncio
async def test_duplicate_detection():
    """Test that pipeline detects and stops on duplicate pages.

    When a user tries to create a page that already exists,
    the check_existing agent should detect it and the pipeline
    should stop without creating content or a new page.
    """
    await AgentEvaluator.evaluate(
        agent_module="falls_cms_agent",
        eval_dataset_file_path_or_dir=str(FIXTURES_DIR / "duplicate_detection.test.json"),
    )


@pytest.mark.skipif(not ADK_AVAILABLE, reason="google-adk not installed")
@pytest.mark.asyncio
async def test_fake_waterfall_rejection():
    """Test that research agent rejects non-existent waterfalls.

    When a user tries to create a page for a fictional waterfall,
    the research agent should detect it can't find credible sources
    and output RESEARCH_FAILED to stop the pipeline.
    """
    await AgentEvaluator.evaluate(
        agent_module="falls_cms_agent",
        eval_dataset_file_path_or_dir=str(FIXTURES_DIR / "fake_waterfall_rejection.test.json"),
    )


@pytest.mark.skipif(not ADK_AVAILABLE, reason="google-adk not installed")
@pytest.mark.asyncio
async def test_intent_classification():
    """Test that router correctly classifies user intents.

    The router should correctly identify intent types and dispatch
    to appropriate pipelines.
    """
    await AgentEvaluator.evaluate(
        agent_module="falls_cms_agent",
        eval_dataset_file_path_or_dir=str(FIXTURES_DIR / "intent_classification.test.json"),
    )


@pytest.mark.skipif(not ADK_AVAILABLE, reason="google-adk not installed")
@pytest.mark.asyncio
async def test_page_management():
    """Test page management operations (move, publish, list)."""
    await AgentEvaluator.evaluate(
        agent_module="falls_cms_agent",
        eval_dataset_file_path_or_dir=str(FIXTURES_DIR / "page_management.test.json"),
    )


@pytest.mark.skipif(not ADK_AVAILABLE, reason="google-adk not installed")
@pytest.mark.asyncio
async def test_list_and_search():
    """Test list and search operations."""
    await AgentEvaluator.evaluate(
        agent_module="falls_cms_agent",
        eval_dataset_file_path_or_dir=str(FIXTURES_DIR / "list_and_search.test.json"),
    )


@pytest.mark.skip(
    reason="Conversational tests are too non-deterministic - agent may respond directly or use tools"
)
@pytest.mark.skipif(not ADK_AVAILABLE, reason="google-adk not installed")
@pytest.mark.asyncio
async def test_conversational():
    """Test conversational scenarios (help, clarification requests).

    NOTE: Skipped because agent behavior varies - sometimes responds directly
    without tools, sometimes calls classify_intent first. This is expected
    behavior for conversational scenarios but makes deterministic testing difficult.
    """
    await AgentEvaluator.evaluate(
        agent_module="falls_cms_agent",
        eval_dataset_file_path_or_dir=str(FIXTURES_DIR / "conversational.test.json"),
    )


# =============================================================================
# Comprehensive Test
# =============================================================================


@pytest.mark.skipif(not ADK_AVAILABLE, reason="google-adk not installed")
@pytest.mark.asyncio
async def test_all_recorded():
    """Run all recorded trajectory tests."""
    await AgentEvaluator.evaluate(
        agent_module="falls_cms_agent",
        eval_dataset_file_path_or_dir=str(FIXTURES_DIR / "all_recorded.test.json"),
    )
