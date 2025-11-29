"""Main agent entry point for Falls Into Love CMS Agent.

This file defines root_agent which is the entry point for ADK.
The agent can be run with: adk web or adk run falls_cms_agent

Architecture:
- root_agent is an LlmAgent with pipeline tools attached
- Each pipeline tool is a FunctionTool that orchestrates sub-agents
- This gives us deterministic control flow (Python code) while staying ADK-compatible
- before_agent_callback captures user_id into ContextVar for event streaming
"""

from google.adk.agents import LlmAgent

from .core.config import Config
from .core.context import set_user_id
from .core.logging import get_logger, setup_logging
from .pipelines import ALL_PIPELINE_TOOLS

# Set up logging
setup_logging()

logger = get_logger(__name__)


def capture_user_context(callback_context) -> None:
    """Capture user_id from ADK context and store in ContextVar.

    This runs at the start of each request, before the LLM processes it.
    The user_id is then available to emit_status_sync() via get_user_id().

    ADK passes input parameters in different places depending on the context:
    - callback_context.state: Session state (if sessions are used)
    - callback_context.session.state: Alternative session location
    - callback_context.invocation_context: The original API input
    """
    user_id = None

    # Log what we have to work with
    logger.info(f"Callback context type: {type(callback_context)}")
    logger.info(f"Callback context attrs: {dir(callback_context)}")

    # Check state first (if using session state)
    if hasattr(callback_context, "state") and callback_context.state:
        logger.info(f"callback_context.state: {callback_context.state}")
        user_id = callback_context.state.get("user_id")

    # Check session.state
    if not user_id and hasattr(callback_context, "session"):
        session = callback_context.session
        if session and hasattr(session, "state") and session.state:
            logger.info(f"callback_context.session.state: {session.state}")
            user_id = session.state.get("user_id")

    # Check invocation_context (where API input parameters often are)
    if not user_id and hasattr(callback_context, "invocation_context"):
        inv_ctx = callback_context.invocation_context
        logger.info(f"invocation_context type: {type(inv_ctx)}")
        if hasattr(inv_ctx, "user_id"):
            user_id = inv_ctx.user_id
        elif isinstance(inv_ctx, dict):
            user_id = inv_ctx.get("user_id")

    # Check user_content for input parameters
    if not user_id and hasattr(callback_context, "user_content"):
        logger.info(f"user_content: {callback_context.user_content}")

    if user_id:
        set_user_id(user_id)
        logger.info(f"Context set: user_id={user_id}")
    else:
        logger.warning("No user_id found in callback context - events will be skipped")


# Root agent instruction - orchestrates pipeline tools
ROOT_INSTRUCTION = """You are the Falls Into Love CMS assistant, helping manage a waterfall photography and hiking blog.

AVAILABLE TOOLS:

**Creating Content:**
- create_waterfall_page: Research and create a new waterfall page with engaging content
  - Requires: waterfall_name (required), parent_name (optional)
  - Example: "Create a page for Multnomah Falls in Oregon"

- create_category_page: Create a category/region page for organizing waterfalls
  - Requires: category_name (required), parent_name (optional)
  - Use for: geographic regions, areas, highways - NOT for actual waterfalls
  - Example: "Create a category called Mount Rainier"

**Managing Pages:**
- move_page: Move a page to a new parent category (parent must exist)
  - Requires: page_name, new_parent_name (or null for root)
  - If parent doesn't exist, create it first with create_category_page
  - Example: "Move Toketee Falls under Highway 138"

- publish_page: Make a draft page live
  - Requires: page_name
  - Example: "Publish Multnomah Falls"

- unpublish_page: Make a published page draft
  - Requires: page_name
  - Example: "Unpublish the Watson Falls page"

- update_page_content: REPLACE a content block on a page (overwrites existing content!)
  - Requires: page_name, block_name, block_content (HTML)
  - ⚠️ This REPLACES the entire block content, it does NOT append/add to existing content
  - If user wants to ADD content: First use get_page_details to see existing content,
    then include both old + new content in the update
  - Block name mapping (user-friendly → actual block name):
    - "hero" or "main image" → cjBlockHero
    - "introduction" or "intro" or "description" → cjBlockIntroduction
    - "hiking tips" or "trail tips" → cjBlockHikingTips
    - "seasonal info" or "best time" or "seasons" → cjBlockSeasonalInfo
    - "photography tips" or "photo tips" → cjBlockPhotographyTips
    - "directions" or "how to get there" → cjBlockDirections
    - "additional info" or "more info" or "extra" → cjBlockAdditionalInfo
    - "gallery" or "photos" → cjBlockGallery
  - Example: "Replace the hero block on Multnomah Falls with new content"

**Searching & Viewing:**
- search_pages: Search for pages by keyword or slug
  - Optional: query, parent_name
  - Supports searching by title OR slug (e.g., "butte-falls-oregon-1")
  - Returns: formatted_list (present this to user as-is), pages array, total_count
  - Example: "Find pages about Oregon"

- list_pages: List all pages or pages under a parent
  - Optional: parent_name
  - Returns: formatted_list (present this to user as-is), pages array, total_count
  - Example: "What pages do we have?"

- get_page_details: Get full details about a page including block content
  - Requires: page_name (can be title OR slug like "butte-falls-oregon-1")
  - Example: "Show me the Multnomah Falls page"

HOW TO RESPOND:

1. For CREATE requests:
   - Extract the waterfall name and optional parent
   - Call create_waterfall_page with those parameters
   - The pipeline handles research, content, and CMS creation

2. For MOVE/PUBLISH/UPDATE requests:
   - Extract the page name and any destination or block info
   - For UPDATE with "add" or "append": First call get_page_details to get existing
     block content, then call update_page_content with old content + new content combined
   - For UPDATE with "replace" or just "update": Call update_page_content directly
   - Report the result

3. For SEARCH/LIST/GET requests:
   - Call the appropriate tool
   - For search/list: Present the formatted_list field directly to the user
   - For get_page_details: Present the returned details as-is

4. For greetings or help:
   - Introduce yourself and explain what you can do
   - Offer examples of commands

CONFIRMATION RULES:
- CREATE/MOVE/PUBLISH/UPDATE: Execute immediately, report results
- If something fails, explain what went wrong
- DELETE is not supported (for safety). If user asks to delete, explain they need to use the CMS admin interface.

IMPORTANT - DO NOT offer multi-step help or ask follow-up questions like:
- "Do you want me to create that category?"
- "Should I also publish the page?"
- "Would you like me to add more content?"
These require conversation state we don't have. Just execute what's asked or explain what failed.

COMMUNICATION STYLE:
- Be concise and friendly
- Report results clearly
- If a page isn't found, suggest searching for similar names
- Don't offer to do additional tasks - let the user ask
"""

# Define the root agent - the main entry point for ADK
root_agent = LlmAgent(
    name="falls_cms_assistant",
    model=Config.DEFAULT_MODEL,
    description="Content assistant for Falls Into Love CMS - creates and manages waterfall pages.",
    instruction=ROOT_INSTRUCTION,
    tools=ALL_PIPELINE_TOOLS,
    before_agent_callback=capture_user_context,
)
