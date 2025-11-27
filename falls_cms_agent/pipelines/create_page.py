"""Create Waterfall Page Pipeline - orchestrates the full page creation workflow.

This module implements the "Tools-as-Pipelines" pattern where the pipeline
function is wrapped as an ADK FunctionTool and orchestrates sub-agents.

Note: Due to ADK Runner app_name mismatch bugs (https://github.com/google/adk-python/issues/3133),
we use google.genai directly for sub-agent calls instead of nested Runners.
"""

from google import genai
from google.adk.tools import FunctionTool
from google.genai import types

from common.schemas import ResearchResult, WaterfallPageDraft

from ..core.callbacks import emit_status_sync
from ..core.config import Config
from ..core.logging import get_logger
from ..core.mcp_client import get_mcp_client
from ..core.prompts import load_prompt

logger = get_logger(__name__)

# Initialize genai client
_client = genai.Client()


async def call_research_llm(prompt: str) -> str | None:
    """Call research LLM with Google Search tool.

    Uses google.genai directly to avoid ADK Runner app_name mismatch issues.
    Uses Gemini's native google_search_retrieval tool for grounding.
    Uses structured output to enforce JSON response format.
    """
    research_instruction = load_prompt("research")

    # Use Gemini's native Google Search grounding tool
    google_search_tool = types.Tool(
        google_search=types.GoogleSearch(),
    )

    # Generate JSON schema from Pydantic model
    research_schema = ResearchResult.model_json_schema()

    config = types.GenerateContentConfig(
        system_instruction=research_instruction,
        tools=[google_search_tool],
        response_mime_type="application/json",
        response_schema=research_schema,
    )

    response = await _client.aio.models.generate_content(
        model=Config.DEFAULT_MODEL,
        contents=prompt,
        config=config,
    )

    if response.text:
        return response.text
    return None


async def call_content_llm(prompt: str) -> str | None:
    """Call content generation LLM.

    Uses google.genai directly to avoid ADK Runner app_name mismatch issues.
    Uses structured output to enforce JSON response format.
    """
    content_instruction = load_prompt("content")
    voice_instruction = load_prompt("voice")

    # Combine content and voice instructions
    full_instruction = f"{content_instruction}\n\n{voice_instruction}"

    # Generate JSON schema from Pydantic model
    content_schema = WaterfallPageDraft.model_json_schema()

    config = types.GenerateContentConfig(
        system_instruction=full_instruction,
        response_mime_type="application/json",
        response_schema=content_schema,
    )

    response = await _client.aio.models.generate_content(
        model=Config.DEFAULT_MODEL,
        contents=prompt,
        config=config,
    )

    if response.text:
        return response.text
    return None


async def check_for_duplicate(waterfall_name: str) -> dict | None:
    """Check if a page with this name already exists.

    Args:
        waterfall_name: Name of the waterfall to check

    Returns:
        Page dict if duplicate found, None otherwise
    """
    try:
        mcp = get_mcp_client()
        pages = await mcp.call_tool("list_pages", {"search": waterfall_name})

        if isinstance(pages, list) and len(pages) > 0:
            # Check for exact or close match
            for page in pages:
                if page.get("title", "").lower() == waterfall_name.lower():
                    return page
        return None
    except Exception as e:
        logger.warning(f"Error checking for duplicates: {e}")
        return None


def _normalize_category_name(name: str) -> str:
    """Normalize category name to title case for proper nouns.

    Handles common geographic naming conventions:
    - "southern oregon" -> "Southern Oregon"
    - "columbia river gorge" -> "Columbia River Gorge"
    - "highway 138" -> "Highway 138"
    """
    # Title case the name
    normalized = name.strip().title()

    # Handle common lowercase words that should stay lowercase in titles
    # (unless they're the first word)
    lowercase_words = {"of", "the", "and", "in", "at", "to", "for", "on"}
    words = normalized.split()
    result = [words[0]]  # Keep first word as-is (title case)
    for word in words[1:]:
        if word.lower() in lowercase_words:
            result.append(word.lower())
        else:
            result.append(word)

    return " ".join(result)


async def find_or_create_parent(
    parent_name: str | None,
    user_id: int | str | None,
) -> int | None:
    """Find existing parent page or create a new category page.

    Args:
        parent_name: Name of the parent/category (e.g., "Oregon")
        user_id: Rails user ID for event streaming

    Returns:
        Parent page ID, or None if no parent specified
    """
    if not parent_name:
        return None

    # Normalize the category name (e.g., "southern oregon" -> "Southern Oregon")
    parent_name = _normalize_category_name(parent_name)

    mcp = get_mcp_client()

    # Search for existing parent
    try:
        pages = await mcp.call_tool("list_pages", {"search": parent_name})

        if isinstance(pages, list):
            for page in pages:
                if page.get("title", "").lower() == parent_name.lower():
                    logger.info(f"Found existing parent: {page['title']} (ID: {page['id']})")
                    return page["id"]

        # Parent not found - create it
        emit_status_sync(user_id, f"Creating category page '{parent_name}'...", "step_start")

        created = await mcp.call_tool(
            "create_category_page",
            {"title": parent_name},
        )
        parent_id = created.get("id") if isinstance(created, dict) else None

        if parent_id:
            logger.info(f"Created parent page: {parent_name} (ID: {parent_id})")
            emit_status_sync(user_id, f"Created '{parent_name}' (ID: {parent_id})", "step_complete")
        else:
            logger.warning(f"Failed to create parent page: {parent_name}")
            emit_status_sync(user_id, f"Failed to create parent page '{parent_name}'", "step_error")

        return parent_id

    except Exception as e:
        logger.warning(f"Error finding/creating parent: {e}")
        return None


async def create_waterfall_page(
    waterfall_name: str,
    parent_name: str | None = None,
    user_id: int | str | None = None,
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
        user_id: Optional Rails user ID for real-time event streaming to UI

    Returns:
        Status message describing what was created or why it stopped
    """
    logger.info(f"Starting create pipeline for: {waterfall_name}")

    # Step 1: Check for duplicates
    emit_status_sync(user_id, "Checking for existing pages...", "step_start")

    duplicate = await check_for_duplicate(waterfall_name)
    if duplicate:
        msg = f"DUPLICATE_FOUND: '{duplicate['title']}' already exists (ID: {duplicate['id']})"
        emit_status_sync(user_id, msg, "pipeline_stopped")
        return msg

    emit_status_sync(user_id, "No duplicate found", "step_complete")

    # Step 2: Research the waterfall
    emit_status_sync(user_id, f"Researching {waterfall_name}...", "step_start")

    try:
        research_text = await call_research_llm(
            f"Research the waterfall called {waterfall_name}. Find GPS coordinates, "
            f"trail distance, elevation gain, difficulty, and notable features."
        )

        if not research_text:
            msg = f"RESEARCH_FAILED: No response from research LLM for {waterfall_name}"
            emit_status_sync(user_id, msg, "pipeline_error")
            return msg

        # Parse research result from JSON response
        try:
            research = ResearchResult.model_validate_json(research_text)
        except Exception as parse_error:
            # LLM returned non-JSON response - this is a failure
            logger.warning(f"Could not parse research as JSON: {parse_error}")
            logger.debug(f"Research text: {research_text[:500]}")
            msg = f"RESEARCH_FAILED: Research returned invalid format. Expected JSON but got: {research_text[:200]}..."
            emit_status_sync(user_id, msg, "pipeline_error")
            return msg

        if not research.verified:
            msg = f"RESEARCH_FAILED: Could not verify '{waterfall_name}' exists. {research.verification_notes or ''}"
            emit_status_sync(user_id, msg, "pipeline_stopped")
            return msg

        emit_status_sync(user_id, "Research complete", "step_complete")

    except Exception as e:
        logger.error(f"Research failed: {e}")
        msg = f"RESEARCH_FAILED: Error researching {waterfall_name}: {e}"
        emit_status_sync(user_id, msg, "pipeline_error")
        return msg

    # Step 3: Generate content with brand voice
    emit_status_sync(user_id, "Writing engaging content...", "step_start")

    try:
        content_text = await call_content_llm(
            f"Create content for {waterfall_name} using this research:\n\n"
            f"{research.model_dump_json(indent=2)}"
        )

        if not content_text:
            msg = f"CONTENT_FAILED: No response from content LLM for {waterfall_name}"
            emit_status_sync(user_id, msg, "pipeline_error")
            return msg

        # Parse content result from JSON response
        try:
            draft = WaterfallPageDraft.model_validate_json(content_text)
        except Exception as parse_error:
            logger.error(f"Could not parse content as WaterfallPageDraft: {parse_error}")
            logger.debug(f"Content text: {content_text[:500]}")
            msg = f"CONTENT_FAILED: Invalid content format: {parse_error}"
            emit_status_sync(user_id, msg, "pipeline_error")
            return msg

        emit_status_sync(user_id, "Content ready", "step_complete")

    except Exception as e:
        logger.error(f"Content generation failed: {e}")
        msg = f"CONTENT_FAILED: Error generating content: {e}"
        emit_status_sync(user_id, msg, "pipeline_error")
        return msg

    # Step 4: Create the page in CMS
    emit_status_sync(user_id, "Creating page in CMS...", "step_start")

    try:
        mcp = get_mcp_client()

        # Find or create parent page
        parent_id = await find_or_create_parent(parent_name, user_id)

        # Convert draft to MCP tool format
        page_data = draft.to_mcp_dict(parent_id=parent_id)

        # Create the page using the MCP create_waterfall_page tool
        created = await mcp.call_tool("create_waterfall_page", page_data)

        page_id = created.get("id") if isinstance(created, dict) else None
        page_title = created.get("title", draft.title) if isinstance(created, dict) else draft.title
        block_count = len(draft.blocks)

        parent_info = f"under '{parent_name}'" if parent_name else "at root level"
        msg = (
            f"SUCCESS: Created '{page_title}' (ID: {page_id}) as draft {parent_info}. "
            f"Included {block_count} content blocks."
        )

        emit_status_sync(user_id, msg, "pipeline_complete")
        logger.info(msg)
        return msg

    except Exception as e:
        logger.error(f"CMS creation failed: {e}")
        msg = f"CMS_ERROR: Failed to create page: {e}"
        emit_status_sync(user_id, msg, "pipeline_error")
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
