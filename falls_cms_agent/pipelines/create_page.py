"""Create Waterfall Page Pipeline - orchestrates the full page creation workflow.

This module implements the "Tools-as-Pipelines" pattern where the pipeline
function is wrapped as an ADK FunctionTool and orchestrates sub-agents.
"""

import json
from typing import Any

from google.adk.tools import FunctionTool

from common.schemas import CategoryPageDraft, ResearchResult, WaterfallPageDraft

from ..agents.cms import get_mcp_toolset
from ..agents.content import content_agent
from ..agents.research import research_agent
from ..core.callbacks import emit_status_sync
from ..core.logging import get_logger

logger = get_logger(__name__)


async def check_for_duplicate(waterfall_name: str, mcp_tools: Any) -> dict | None:
    """Check if a page with this name already exists.

    Args:
        waterfall_name: Name of the waterfall to check
        mcp_tools: MCP toolset instance

    Returns:
        Page dict if duplicate found, None otherwise
    """
    # Use the list_pages tool to search
    try:
        result = await mcp_tools.call_tool("list_pages", {"search": waterfall_name})
        pages = json.loads(result) if isinstance(result, str) else result

        if isinstance(pages, list) and len(pages) > 0:
            # Check for exact or close match
            for page in pages:
                if page.get("title", "").lower() == waterfall_name.lower():
                    return page
        return None
    except Exception as e:
        logger.warning(f"Error checking for duplicates: {e}")
        return None


async def find_or_create_parent(
    parent_name: str | None,
    mcp_tools: Any,
    session_id: str | None,
) -> int | None:
    """Find existing parent page or create a new category page.

    Args:
        parent_name: Name of the parent/category (e.g., "Oregon")
        mcp_tools: MCP toolset instance
        session_id: Session ID for event streaming

    Returns:
        Parent page ID, or None if no parent specified
    """
    if not parent_name:
        return None

    # Search for existing parent
    try:
        result = await mcp_tools.call_tool("list_pages", {"search": parent_name})
        pages = json.loads(result) if isinstance(result, str) else result

        if isinstance(pages, list):
            for page in pages:
                if page.get("title", "").lower() == parent_name.lower():
                    logger.info(f"Found existing parent: {page['title']} (ID: {page['id']})")
                    return page["id"]

        # Parent not found - create it
        emit_status_sync(session_id, f"Creating category page '{parent_name}'...")
        draft = CategoryPageDraft(title=parent_name)

        create_result = await mcp_tools.call_tool(
            "create_category_page",
            {"draft": draft.model_dump()},
        )
        created = json.loads(create_result) if isinstance(create_result, str) else create_result
        parent_id = created.get("id")
        logger.info(f"Created parent page: {parent_name} (ID: {parent_id})")
        return parent_id

    except Exception as e:
        logger.warning(f"Error finding/creating parent: {e}")
        return None


async def create_waterfall_page(
    waterfall_name: str,
    parent_name: str | None = None,
    session_id: str | None = None,
) -> str:
    """Research and create a new waterfall page with engaging content.

    This function orchestrates:
    1. Duplicate check
    2. Research via google_search
    3. Content generation with brand voice
    4. CMS page creation

    Args:
        waterfall_name: Name of the waterfall to create a page for (e.g., "Multnomah Falls")
        parent_name: Optional parent/category name (e.g., "Oregon")
        session_id: Optional session ID for real-time event streaming (internal use)

    Returns:
        Status message describing what was created or why it stopped
    """
    logger.info(f"Starting create pipeline for: {waterfall_name}")
    mcp_tools = get_mcp_toolset()

    # Step 1: Check for duplicates
    emit_status_sync(session_id, "Checking for existing pages...", "step_start")

    duplicate = await check_for_duplicate(waterfall_name, mcp_tools)
    if duplicate:
        msg = f"DUPLICATE_FOUND: '{duplicate['title']}' already exists (ID: {duplicate['id']})"
        emit_status_sync(session_id, msg, "pipeline_stopped")
        return msg

    emit_status_sync(session_id, "No duplicate found", "step_complete")

    # Step 2: Research the waterfall
    emit_status_sync(session_id, f"Researching {waterfall_name}...", "step_start")

    try:
        research_result = await research_agent.run_async(
            f"Research the waterfall called {waterfall_name}. Find GPS coordinates, "
            f"trail distance, elevation gain, difficulty, and notable features."
        )

        # Parse research result
        if isinstance(research_result, ResearchResult):
            research = research_result
        elif isinstance(research_result, str):
            research = ResearchResult.model_validate_json(research_result)
        else:
            research = ResearchResult.model_validate(research_result)

        if not research.verified:
            msg = f"RESEARCH_FAILED: Could not verify '{waterfall_name}' exists. {research.verification_notes or ''}"
            emit_status_sync(session_id, msg, "pipeline_stopped")
            return msg

        emit_status_sync(session_id, "Research complete", "step_complete")

    except Exception as e:
        logger.error(f"Research failed: {e}")
        msg = f"RESEARCH_FAILED: Error researching {waterfall_name}: {e}"
        emit_status_sync(session_id, msg, "pipeline_error")
        return msg

    # Step 3: Generate content with brand voice
    emit_status_sync(session_id, "Writing engaging content...", "step_start")

    try:
        content_result = await content_agent.run_async(
            f"Create content for {waterfall_name} using this research:\n\n"
            f"{research.model_dump_json(indent=2)}"
        )

        # Parse content result
        if isinstance(content_result, WaterfallPageDraft):
            draft = content_result
        elif isinstance(content_result, str):
            draft = WaterfallPageDraft.model_validate_json(content_result)
        else:
            draft = WaterfallPageDraft.model_validate(content_result)

        emit_status_sync(session_id, "Content ready", "step_complete")

    except Exception as e:
        logger.error(f"Content generation failed: {e}")
        msg = f"CONTENT_FAILED: Error generating content: {e}"
        emit_status_sync(session_id, msg, "pipeline_error")
        return msg

    # Step 4: Create the page in CMS
    emit_status_sync(session_id, "Creating page in CMS...", "step_start")

    try:
        # Find or create parent page
        parent_id = await find_or_create_parent(parent_name, mcp_tools, session_id)

        # Convert draft to API format
        page_data = draft.to_api_dict(parent_id=parent_id)

        # Create the page
        create_result = await mcp_tools.call_tool("create_waterfall_page", {"draft": page_data})
        created = json.loads(create_result) if isinstance(create_result, str) else create_result

        page_id = created.get("id")
        page_title = created.get("title", draft.title)
        block_count = len(draft.blocks)

        parent_info = f"under '{parent_name}'" if parent_name else "at root level"
        msg = (
            f"SUCCESS: Created '{page_title}' (ID: {page_id}) as draft {parent_info}. "
            f"Included {block_count} content blocks."
        )

        emit_status_sync(session_id, msg, "pipeline_complete")
        logger.info(msg)
        return msg

    except Exception as e:
        logger.error(f"CMS creation failed: {e}")
        msg = f"CMS_ERROR: Failed to create page: {e}"
        emit_status_sync(session_id, msg, "pipeline_error")
        return msg


# Wrap as ADK FunctionTool for use by root agent
# Note: FunctionTool extracts name and description from the function itself
create_pipeline_tool = FunctionTool(func=create_waterfall_page)


# Also export the agents used by this pipeline for direct access if needed
__all__ = [
    "create_waterfall_page",
    "create_pipeline_tool",
    "check_for_duplicate",
    "find_or_create_parent",
]
