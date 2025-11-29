"""Create Waterfall Page Pipeline - orchestrates the full page creation workflow.

This module implements the "Tools-as-Pipelines" pattern where the pipeline
function is wrapped as an ADK FunctionTool and orchestrates sub-agents.

Note: Due to ADK Runner app_name mismatch bugs (https://github.com/google/adk-python/issues/3133),
we use google.genai directly for sub-agent calls instead of nested Runners.
"""

from google import genai
from google.adk.tools import FunctionTool, ToolContext
from google.genai import types

from ..common.schemas import ResearchResult, WaterfallPageDraft
from ..core.callbacks import emit_status_sync
from ..core.config import Config
from ..core.context import set_user_id
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

    # Generate JSON schema from Pydantic model
    content_schema = WaterfallPageDraft.model_json_schema()

    config = types.GenerateContentConfig(
        system_instruction=content_instruction,
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


async def find_or_create_parent(parent_name: str | None) -> int | None:
    """Find existing parent page or create a new category page.

    Args:
        parent_name: Name of the parent/category (e.g., "Oregon")

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
        emit_status_sync(f"Creating category page '{parent_name}'...", "step_start")

        created = await mcp.call_tool(
            "create_category_page",
            {"title": parent_name},
        )
        parent_id = created.get("id") if isinstance(created, dict) else None

        if parent_id:
            logger.info(f"Created parent page: {parent_name} (ID: {parent_id})")
            emit_status_sync(f"Created '{parent_name}' (ID: {parent_id})", "step_complete")
        else:
            logger.warning(f"Failed to create parent page: {parent_name}")
            emit_status_sync(f"Failed to create parent page '{parent_name}'", "step_error")

        return parent_id

    except Exception as e:
        logger.warning(f"Error finding/creating parent: {e}")
        return None


async def create_waterfall_page(
    waterfall_name: str,
    parent_name: str | None = None,
    tool_context: ToolContext | None = None,
) -> str:
    """Research and create a new waterfall page with engaging content.

    This function orchestrates:
    1. Duplicate check
    2. Research via google_search
    3. Content generation with brand voice
    4. CMS page creation

    The tool_context is injected by ADK and contains state including user_id.

    Args:
        waterfall_name: Name of the waterfall to create a page for (e.g., "Multnomah Falls")
        parent_name: Optional parent/category name (e.g., "Oregon")
        tool_context: Injected by ADK - contains state with user_id for event streaming

    Returns:
        Status message describing what was created or why it stopped
    """
    logger.info("=" * 60)
    logger.info("[PIPELINE] create_waterfall_page STARTED")
    logger.info(f"[PIPELINE] waterfall_name={waterfall_name}, parent_name={parent_name}")
    logger.info(f"[PIPELINE] tool_context type: {type(tool_context)}")

    # Extract user_id from tool_context and set in ContextVar for emit_status_sync
    # ADK puts user_id directly on tool_context as an attribute (not in state!)
    user_id = None

    if tool_context:
        # ADK provides user_id directly on tool_context
        if hasattr(tool_context, "user_id"):
            user_id = tool_context.user_id
            logger.info(f"[PIPELINE] tool_context.user_id = {user_id}")

        if user_id:
            set_user_id(user_id)
            logger.info(f"[PIPELINE] SUCCESS: Set user_id={user_id} in ContextVar")
        else:
            logger.warning("[PIPELINE] PROBLEM: tool_context.user_id is None or missing")
    else:
        logger.warning("[PIPELINE] PROBLEM: tool_context is None")

    logger.info(f"[PIPELINE] Starting create pipeline for: {waterfall_name}")

    # Step 1: Check for duplicates
    logger.info("[PIPELINE] Step 1: Checking for duplicates")
    emit_status_sync("Checking for existing pages...", "step_start")

    duplicate = await check_for_duplicate(waterfall_name)
    if duplicate:
        msg = f"DUPLICATE_FOUND: '{duplicate['title']}' already exists (ID: {duplicate['id']})"
        logger.info(f"[PIPELINE] Duplicate found, stopping: {msg}")
        emit_status_sync(msg, "pipeline_stopped")
        return msg

    logger.info("[PIPELINE] Step 1 complete: No duplicate found")
    emit_status_sync("No duplicate found", "step_complete")

    # Step 2: Research the waterfall
    logger.info("[PIPELINE] Step 2: Starting research")
    emit_status_sync(f"Researching {waterfall_name}...", "step_start")

    try:
        research_text = await call_research_llm(
            f"Research the waterfall called {waterfall_name}. Find GPS coordinates, "
            f"trail distance, elevation gain, difficulty, and notable features."
        )

        if not research_text:
            msg = f"RESEARCH_FAILED: No response from research LLM for {waterfall_name}"
            emit_status_sync(msg, "pipeline_error")
            return msg

        # Parse research result from JSON response
        try:
            research = ResearchResult.model_validate_json(research_text)
        except Exception as parse_error:
            # LLM returned non-JSON response - this is a failure
            logger.warning(f"Could not parse research as JSON: {parse_error}")
            logger.debug(f"Research text: {research_text[:500]}")
            msg = f"RESEARCH_FAILED: Research returned invalid format. Expected JSON but got: {research_text[:200]}..."
            emit_status_sync(msg, "pipeline_error")
            return msg

        if not research.verified:
            msg = f"RESEARCH_FAILED: Could not verify '{waterfall_name}' exists. {research.verification_notes or ''}"
            emit_status_sync(msg, "pipeline_stopped")
            return msg

        logger.info("[PIPELINE] Step 2 complete: Research successful")
        emit_status_sync("Research complete", "step_complete")

    except Exception as e:
        logger.error(f"[PIPELINE] Step 2 failed: {e}")
        msg = f"RESEARCH_FAILED: Error researching {waterfall_name}: {e}"
        emit_status_sync(msg, "pipeline_error")
        return msg

    # Step 3: Generate content with brand voice
    logger.info("[PIPELINE] Step 3: Generating content")
    emit_status_sync("Writing engaging content...", "step_start")

    try:
        content_text = await call_content_llm(
            f"Create content for {waterfall_name} using this research:\n\n"
            f"{research.model_dump_json(indent=2)}"
        )

        if not content_text:
            msg = f"CONTENT_FAILED: No response from content LLM for {waterfall_name}"
            emit_status_sync(msg, "pipeline_error")
            return msg

        # Parse content result from JSON response
        try:
            draft = WaterfallPageDraft.model_validate_json(content_text)
        except Exception as parse_error:
            logger.error(f"Could not parse content as WaterfallPageDraft: {parse_error}")
            logger.debug(f"Content text: {content_text[:500]}")
            msg = f"CONTENT_FAILED: Invalid content format: {parse_error}"
            emit_status_sync(msg, "pipeline_error")
            return msg

        logger.info("[PIPELINE] Step 3 complete: Content generated")
        emit_status_sync("Content ready", "step_complete")

    except Exception as e:
        logger.error(f"[PIPELINE] Step 3 failed: {e}")
        msg = f"CONTENT_FAILED: Error generating content: {e}"
        emit_status_sync(msg, "pipeline_error")
        return msg

    # Step 4: Create the page in CMS
    logger.info("[PIPELINE] Step 4: Creating page in CMS")
    emit_status_sync("Creating page in CMS...", "step_start")

    try:
        mcp = get_mcp_client()

        # Find or create parent page
        parent_id = await find_or_create_parent(parent_name)

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

        logger.info(f"[PIPELINE] Step 4 complete: Page created - {msg}")
        emit_status_sync(msg, "pipeline_complete")
        logger.info("[PIPELINE] ========== PIPELINE COMPLETED SUCCESSFULLY ==========")
        return msg

    except Exception as e:
        logger.error(f"[PIPELINE] Step 4 failed: {e}")
        msg = f"CMS_ERROR: Failed to create page: {e}"
        emit_status_sync(msg, "pipeline_error")
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
