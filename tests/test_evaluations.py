"""ADK evaluation tests for Falls CMS Agent.

These tests use ADK's AgentEvaluator to verify agent behavior
matches expected tool trajectories and responses.

Run with: pytest tests/test_evaluations.py -v
"""

import pytest
from pathlib import Path

# Note: These imports will work once google-adk is installed
try:
    from google.adk.evaluation.agent_evaluator import AgentEvaluator
    ADK_AVAILABLE = True
except ImportError:
    ADK_AVAILABLE = False


FIXTURES_DIR = Path(__file__).parent / "fixtures"


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
async def test_parent_page_assignment():
    """Test that pages are created under correct parent.

    When user specifies a parent category (e.g., "in the Waterfalls category"),
    the pipeline should look up that parent page and set parent_id correctly.
    """
    await AgentEvaluator.evaluate(
        agent_module="falls_cms_agent",
        eval_dataset_file_path_or_dir=str(FIXTURES_DIR / "parent_page_assignment.test.json"),
    )


@pytest.mark.skipif(not ADK_AVAILABLE, reason="google-adk not installed")
@pytest.mark.asyncio
async def test_content_blocks():
    """Test that content is created with correct Template 4 blocks.

    Content should use Template 4 block names: cjBlockHero, cjBlockIntroduction,
    cjBlockHikingTips, cjBlockSeasonalInfo, etc.
    """
    await AgentEvaluator.evaluate(
        agent_module="falls_cms_agent",
        eval_dataset_file_path_or_dir=str(FIXTURES_DIR / "content_blocks.test.json"),
    )


# Alternative: Run all tests in fixtures directory
@pytest.mark.skipif(not ADK_AVAILABLE, reason="google-adk not installed")
@pytest.mark.asyncio
async def test_all_fixtures():
    """Run all test fixtures in the fixtures directory."""
    await AgentEvaluator.evaluate(
        agent_module="falls_cms_agent",
        eval_dataset_file_path_or_dir=str(FIXTURES_DIR),
    )
