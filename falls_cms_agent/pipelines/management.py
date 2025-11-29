"""Page Management Pipelines - tools for move, delete, publish, and update operations.

These are simpler pipelines that don't require research or content generation.
They interact directly with the CMS via the MCP SDK client.
"""

import re
from typing import Any

from google.adk.tools import FunctionTool, ToolContext

from ..common.schemas import ContentBlock, PageListResult, PageSummary
from ..core.callbacks import emit_status_sync
from ..core.context import set_user_id
from ..core.logging import get_logger
from ..core.mcp_client import get_mcp_client

logger = get_logger(__name__)


def _init_user_context(tool_context: ToolContext | None) -> None:
    """Extract user_id from ToolContext and set in ContextVar for event streaming.

    ADK injects ToolContext with user_id as a direct attribute.
    We store it in a ContextVar so emit_status_sync() can access it.
    """
    if tool_context and hasattr(tool_context, "user_id") and tool_context.user_id:
        set_user_id(tool_context.user_id)
        logger.debug(f"Set user_id={tool_context.user_id} from ToolContext")


async def find_page_by_name(page_name: str) -> dict | None:
    """Find a page by name or slug.

    Searches for pages matching the input, trying:
    1. Exact title match (case-insensitive)
    2. Exact slug match (for inputs like "butte-falls-oregon")
    3. First search result if no exact match

    Args:
        page_name: Name/title or slug of the page to find

    Returns:
        Page dict if found, None otherwise
    """
    try:
        mcp = get_mcp_client()
        pages = await mcp.call_tool("list_pages", {"search": page_name})

        if isinstance(pages, list):
            search_lower = page_name.lower()

            # Try exact title match first
            for page in pages:
                if page.get("title", "").lower() == search_lower:
                    return page

            # Try exact slug match (for inputs like "butte-falls-oregon-1")
            for page in pages:
                if page.get("slug", "").lower() == search_lower:
                    return page

            # Return first result if no exact match
            if pages:
                return pages[0]
        return None
    except Exception as e:
        logger.warning(f"Error finding page '{page_name}': {e}")
        return None


# =============================================================================
# Create Category Page Pipeline
# =============================================================================


async def create_category_page(
    category_name: str,
    parent_name: str | None = None,
    tool_context: ToolContext | None = None,
) -> str:
    """Create a new category page for organizing waterfall pages.

    Categories are simple pages without waterfall-specific content (no research,
    no trail info). Use this for geographic regions like "Oregon", "Washington",
    or sub-regions like "Columbia River Gorge".

    Args:
        category_name: Name of the category (e.g., "Oregon", "Mount Rainier")
        parent_name: Optional parent category to nest under
        tool_context: Injected by ADK - contains user_id for event streaming

    Returns:
        Status message with the created category ID
    """
    _init_user_context(tool_context)
    logger.info(f"Creating category '{category_name}'")
    mcp = get_mcp_client()

    # Check if category already exists
    emit_status_sync(f"Checking if '{category_name}' exists...", "step_start")
    existing = await find_page_by_name(category_name)
    if existing:
        return f"INFO: Category '{category_name}' already exists (ID: {existing['id']})"
    emit_status_sync("Category doesn't exist yet", "step_complete")

    # Find parent if specified
    parent_id = None
    if parent_name:
        emit_status_sync(f"Finding parent '{parent_name}'...", "step_start")
        parent = await find_page_by_name(parent_name)
        if not parent:
            return f"ERROR: Could not find parent '{parent_name}'"
        parent_id = parent["id"]
        emit_status_sync(f"Found parent (ID: {parent_id})", "step_complete")

    # Create the category
    emit_status_sync(f"Creating category '{category_name}'...", "step_start")
    try:
        params = {"title": category_name}
        if parent_id:
            params["parent_id"] = parent_id

        created = await mcp.call_tool("create_category_page", params)
        category_id = created.get("id") if isinstance(created, dict) else None

        if category_id:
            parent_info = f" under '{parent_name}'" if parent_name else ""
            msg = f"SUCCESS: Created category '{category_name}' (ID: {category_id}){parent_info}"
            emit_status_sync(msg, "pipeline_complete")
            return msg
        else:
            msg = f"ERROR: Failed to create category '{category_name}'"
            emit_status_sync(msg, "pipeline_error")
            return msg

    except Exception as e:
        msg = f"ERROR: Failed to create category: {e}"
        emit_status_sync(msg, "pipeline_error")
        return msg


create_category_pipeline_tool = FunctionTool(func=create_category_page)


# =============================================================================
# Move Page Pipeline
# =============================================================================


async def move_page(
    page_name: str,
    new_parent_name: str | None,
    tool_context: ToolContext | None = None,
) -> str:
    """Move a page to a new parent or to root level.

    The parent must already exist. Use create_category_page first if needed.

    Args:
        page_name: Name of the page to move
        new_parent_name: Name of the new parent (None for root level)
        tool_context: Injected by ADK - contains user_id for event streaming

    Returns:
        Status message
    """
    _init_user_context(tool_context)
    logger.info(f"Moving page '{page_name}' to '{new_parent_name or 'root'}'")
    mcp = get_mcp_client()

    # Find the page to move
    emit_status_sync(f"Finding '{page_name}'...", "step_start")
    page = await find_page_by_name(page_name)
    if not page:
        return f"ERROR: Could not find page '{page_name}'"

    page_id = page["id"]
    emit_status_sync(f"Found page (ID: {page_id})", "step_complete")

    # Find the new parent
    new_parent_id = None
    if new_parent_name:
        emit_status_sync(f"Finding parent '{new_parent_name}'...", "step_start")
        parent = await find_page_by_name(new_parent_name)
        if not parent:
            return f"ERROR: Could not find parent page '{new_parent_name}'. Create it first with create_category_page."
        new_parent_id = parent["id"]
        emit_status_sync(f"Found parent (ID: {new_parent_id})", "step_complete")

    # Execute the move
    emit_status_sync("Moving page...", "step_start")
    try:
        await mcp.call_tool(
            "move_page",
            {
                "page_id": page_id,
                "new_parent_id": new_parent_id,
            },
        )

        dest = f"under '{new_parent_name}'" if new_parent_name else "to root level"
        msg = f"SUCCESS: Moved '{page['title']}' {dest}"
        emit_status_sync(msg, "pipeline_complete")
        return msg

    except Exception as e:
        msg = f"ERROR: Failed to move page: {e}"
        emit_status_sync(msg, "pipeline_error")
        return msg


move_pipeline_tool = FunctionTool(func=move_page)


# =============================================================================
# Publish/Unpublish Pipeline
# =============================================================================


async def run_publish_pipeline(
    page_name: str,
    publish: bool = True,
    tool_context: ToolContext | None = None,
) -> str:
    """Publish or unpublish a page.

    Args:
        page_name: Name of the page
        publish: True to publish, False to unpublish
        tool_context: Injected by ADK - contains user_id for event streaming

    Returns:
        Status message
    """
    _init_user_context(tool_context)
    action = "Publishing" if publish else "Unpublishing"
    logger.info(f"{action} page '{page_name}'")
    mcp = get_mcp_client()

    # Find the page
    emit_status_sync(f"Finding '{page_name}'...", "step_start")
    page = await find_page_by_name(page_name)
    if not page:
        return f"ERROR: Could not find page '{page_name}'"

    page_id = page["id"]
    page_title = page["title"]
    emit_status_sync(f"Found '{page_title}' (ID: {page_id})", "step_complete")

    # Check current state
    is_published = page.get("published", False)
    if is_published == publish:
        state = "published" if publish else "draft"
        return f"INFO: '{page_title}' is already {state}"

    # Update publish state
    emit_status_sync(f"{action}...", "step_start")
    try:
        tool = "publish_page" if publish else "unpublish_page"
        await mcp.call_tool(tool, {"page_id": page_id})

        state = "published" if publish else "draft"
        msg = f"SUCCESS: '{page_title}' is now {state}"
        emit_status_sync(msg, "pipeline_complete")
        return msg

    except Exception as e:
        msg = f"ERROR: Failed to {action.lower()} page: {e}"
        emit_status_sync(msg, "pipeline_error")
        return msg


async def publish_page(
    page_name: str,
    tool_context: ToolContext | None = None,
) -> str:
    """Publish a draft page to make it live on the website."""
    return await run_publish_pipeline(page_name, publish=True, tool_context=tool_context)


async def unpublish_page(
    page_name: str,
    tool_context: ToolContext | None = None,
) -> str:
    """Unpublish a page, reverting it to draft status."""
    return await run_publish_pipeline(page_name, publish=False, tool_context=tool_context)


publish_pipeline_tool = FunctionTool(func=publish_page)

unpublish_pipeline_tool = FunctionTool(func=unpublish_page)


# =============================================================================
# Update Content Pipeline
# =============================================================================


async def update_page_content(
    page_name: str,
    block_name: str,
    block_content: str,
    tool_context: ToolContext | None = None,
) -> str:
    """Update a single content block on a page.

    Args:
        page_name: Name of the page to update
        block_name: Name of the block to update (e.g., 'cjBlockHero')
        block_content: HTML content for the block
        tool_context: Injected by ADK - contains user_id for event streaming

    Returns:
        Status message
    """
    _init_user_context(tool_context)
    logger.info(f"Updating content for '{page_name}'")
    mcp = get_mcp_client()

    # Find the page
    emit_status_sync(f"Finding '{page_name}'...", "step_start")
    page = await find_page_by_name(page_name)
    if not page:
        return f"ERROR: Could not find page '{page_name}'"

    page_id = page["id"]
    page_title = page["title"]
    emit_status_sync(f"Found '{page_title}' (ID: {page_id})", "step_complete")

    # Update block
    emit_status_sync(f"Updating block '{block_name}'...", "step_start")
    try:
        # Validate block
        validated_block = ContentBlock(name=block_name, content=block_content).model_dump()

        await mcp.call_tool(
            "update_page_content",
            {
                "page_id": page_id,
                "blocks": [validated_block],
            },
        )

        msg = f"SUCCESS: Updated block '{block_name}' on '{page_title}'"
        emit_status_sync(msg, "pipeline_complete")
        return msg

    except Exception as e:
        msg = f"ERROR: Failed to update content: {e}"
        emit_status_sync(msg, "pipeline_error")
        return msg


update_content_pipeline_tool = FunctionTool(func=update_page_content)


# =============================================================================
# Search/List Pipelines
# =============================================================================


async def search_pages(
    query: str | None = None,
    parent_name: str | None = None,
    top_level_only: bool = False,
    tool_context: ToolContext | None = None,
) -> dict:
    """Search for pages by keyword or filter by parent category.

    Returns structured data that can be used for follow-up operations.

    Args:
        query: Optional search term
        parent_name: Optional parent page name to filter by
        top_level_only: If True, only return top-level/parent pages (pages without
            a parent). Use this when user asks for "parent pages", "top-level pages",
            "root pages", or "pages without a parent".
        tool_context: Injected by ADK - contains user_id for event streaming

    Returns:
        Dict with 'pages' (list of page summaries), 'total_count', and 'filter_applied'
    """
    _init_user_context(tool_context)
    logger.info(
        f"Searching pages: query='{query}', parent='{parent_name}', top_level={top_level_only}"
    )
    mcp = get_mcp_client()

    emit_status_sync("Searching...", "step_start")

    try:
        params: dict[str, Any] = {}
        filter_parts = []

        if query:
            params["search"] = query
            filter_parts.append(f"search: '{query}'")

        if top_level_only:
            # Get pages without a parent (orphan/root pages)
            params["parent_id"] = "root"
            filter_parts.append("top-level pages only (no parent)")
        elif parent_name:
            # Find parent ID first
            parent = await find_page_by_name(parent_name)
            if parent:
                params["parent_id"] = str(parent["id"])
                filter_parts.append(f"under parent: '{parent_name}'")

        filter_applied = ", ".join(filter_parts) if filter_parts else "all pages"

        raw_pages = await mcp.call_tool("list_pages", params)

        if not raw_pages:
            emit_status_sync("No pages found", "pipeline_complete")
            return PageListResult.create(pages=[], filter_applied=filter_applied).model_dump()

        # Parse into structured PageSummary objects
        pages = [PageSummary.from_api_dict(p) for p in raw_pages]

        emit_status_sync(f"Found {len(pages)} pages", "pipeline_complete")
        return PageListResult.create(
            pages=pages,
            filter_applied=filter_applied,
        ).model_dump()

    except Exception as e:
        msg = f"ERROR: Search failed: {e}"
        emit_status_sync(msg, "pipeline_error")
        # Return empty result on error rather than raising
        return PageListResult.create(pages=[], filter_applied=f"error: {e}").model_dump()


search_pipeline_tool = FunctionTool(func=search_pages)


async def list_pages(
    parent_name: str | None = None,
    top_level_only: bool = False,
    tool_context: ToolContext | None = None,
) -> dict:
    """List all pages or pages under a specific parent category.

    Returns structured data that can be used for follow-up operations.

    Args:
        parent_name: Optional parent to list children of
        top_level_only: If True, only return top-level/parent pages (pages without
            a parent). Use this when user asks for "parent pages", "top-level pages",
            "root pages", or "pages without a parent".
        tool_context: Injected by ADK - contains user_id for event streaming

    Returns:
        Dict with 'pages' (list of page summaries), 'total_count', and 'filter_applied'
    """
    return await search_pages(
        query=None,
        parent_name=parent_name,
        top_level_only=top_level_only,
        tool_context=tool_context,
    )


list_pipeline_tool = FunctionTool(func=list_pages)


async def get_page_details(
    page_name: str,
    tool_context: ToolContext | None = None,
) -> str:
    """Get detailed information about a specific page including blocks and metadata.

    Args:
        page_name: Name of the page to get
        tool_context: Injected by ADK - contains user_id for event streaming

    Returns:
        Formatted page details
    """
    _init_user_context(tool_context)
    logger.info(f"Getting details for '{page_name}'")
    mcp = get_mcp_client()

    emit_status_sync(f"Finding '{page_name}'...", "step_start")
    page = await find_page_by_name(page_name)
    if not page:
        return f"ERROR: Could not find page '{page_name}'"

    # Get full details
    try:
        details = await mcp.call_tool("get_page", {"page_id": page["id"]})

        # Format output
        lines = [
            f"Page: {details.get('title')}",
            f"ID: {details.get('id')}",
            f"Slug: {details.get('slug')}",
            f"Status: {'Published' if details.get('published') else 'Draft'}",
        ]

        if details.get("difficulty"):
            lines.append(f"Difficulty: {details['difficulty']}")
        if details.get("distance"):
            lines.append(f"Distance: {details['distance']} miles")
        if details.get("elevation_gain"):
            lines.append(f"Elevation: {details['elevation_gain']} ft")

        blocks = details.get("blocks", [])
        if blocks:
            lines.append(f"\nContent Blocks ({len(blocks)}):")
            for block in blocks:
                block_name = block.get("name", "unknown")
                block_content = block.get("content", "")
                # Show block name and content (truncate if very long)
                if block_content:
                    # Strip HTML tags for cleaner display
                    clean_content = re.sub(r"<[^>]+>", " ", block_content)
                    clean_content = " ".join(clean_content.split())  # Normalize whitespace
                    preview = (
                        clean_content[:200] + "..." if len(clean_content) > 200 else clean_content
                    )
                    lines.append(f"  - {block_name}: {preview}")
                else:
                    lines.append(f"  - {block_name}: (empty)")

        msg = "\n".join(lines)
        emit_status_sync("Details retrieved", "pipeline_complete")
        return msg

    except Exception as e:
        msg = f"ERROR: Failed to get page details: {e}"
        emit_status_sync(msg, "pipeline_error")
        return msg


get_page_pipeline_tool = FunctionTool(func=get_page_details)


# Export all tools
__all__ = [
    "move_pipeline_tool",
    "publish_pipeline_tool",
    "unpublish_pipeline_tool",
    "update_content_pipeline_tool",
    "search_pipeline_tool",
    "list_pipeline_tool",
    "get_page_pipeline_tool",
    "find_page_by_name",
]
