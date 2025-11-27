"""Page Management Pipelines - tools for move, delete, publish, and update operations.

These are simpler pipelines that don't require research or content generation.
They interact directly with the CMS via the MCP SDK client.
"""

from typing import Any

from google.adk.tools import FunctionTool

from common.schemas import ContentBlock

from ..core.callbacks import emit_status_sync
from ..core.logging import get_logger
from ..core.mcp_client import get_mcp_client

logger = get_logger(__name__)


async def find_page_by_name(page_name: str) -> dict | None:
    """Find a page by name using search.

    Args:
        page_name: Name/title of the page to find

    Returns:
        Page dict if found, None otherwise
    """
    try:
        mcp = get_mcp_client()
        pages = await mcp.call_tool("list_pages", {"search": page_name})

        if isinstance(pages, list):
            # Try exact match first
            for page in pages:
                if page.get("title", "").lower() == page_name.lower():
                    return page
            # Return first result if no exact match
            if pages:
                return pages[0]
        return None
    except Exception as e:
        logger.warning(f"Error finding page '{page_name}': {e}")
        return None


# =============================================================================
# Move Page Pipeline
# =============================================================================


async def move_page(
    page_name: str,
    new_parent_name: str | None,
    session_id: str | None = None,
) -> str:
    """Move a page to a new parent or to root level.

    Args:
        page_name: Name of the page to move
        new_parent_name: Name of the new parent (None for root level)
        session_id: Optional session ID for event streaming

    Returns:
        Status message
    """
    logger.info(f"Moving page '{page_name}' to '{new_parent_name or 'root'}'")
    mcp = get_mcp_client()

    # Find the page to move
    emit_status_sync(session_id, f"Finding '{page_name}'...", "step_start")
    page = await find_page_by_name(page_name)
    if not page:
        return f"ERROR: Could not find page '{page_name}'"

    page_id = page["id"]
    emit_status_sync(session_id, f"Found page (ID: {page_id})", "step_complete")

    # Find or resolve new parent
    new_parent_id = None
    if new_parent_name:
        emit_status_sync(session_id, f"Finding parent '{new_parent_name}'...", "step_start")
        parent = await find_page_by_name(new_parent_name)
        if not parent:
            return f"ERROR: Could not find parent page '{new_parent_name}'"
        new_parent_id = parent["id"]
        emit_status_sync(session_id, f"Found parent (ID: {new_parent_id})", "step_complete")

    # Execute the move
    emit_status_sync(session_id, "Moving page...", "step_start")
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
        emit_status_sync(session_id, msg, "pipeline_complete")
        return msg

    except Exception as e:
        msg = f"ERROR: Failed to move page: {e}"
        emit_status_sync(session_id, msg, "pipeline_error")
        return msg


move_pipeline_tool = FunctionTool(func=move_page)


# =============================================================================
# Delete Page Pipeline
# =============================================================================


async def delete_page(
    page_name: str,
    session_id: str | None = None,
) -> str:
    """Permanently delete a page from the CMS. This cannot be undone.

    Args:
        page_name: Name of the page to delete
        session_id: Optional session ID for event streaming

    Returns:
        Status message
    """
    logger.info(f"Deleting page '{page_name}'")
    mcp = get_mcp_client()

    # Find the page
    emit_status_sync(session_id, f"Finding '{page_name}'...", "step_start")
    page = await find_page_by_name(page_name)
    if not page:
        return f"ERROR: Could not find page '{page_name}'"

    page_id = page["id"]
    page_title = page["title"]
    emit_status_sync(session_id, f"Found '{page_title}' (ID: {page_id})", "step_complete")

    # Delete the page
    emit_status_sync(session_id, "Deleting page...", "step_start")
    try:
        await mcp.call_tool("delete_page", {"page_id": page_id})

        msg = f"SUCCESS: Deleted '{page_title}' (ID: {page_id})"
        emit_status_sync(session_id, msg, "pipeline_complete")
        return msg

    except Exception as e:
        msg = f"ERROR: Failed to delete page: {e}"
        emit_status_sync(session_id, msg, "pipeline_error")
        return msg


delete_pipeline_tool = FunctionTool(func=delete_page)


# =============================================================================
# Publish/Unpublish Pipeline
# =============================================================================


async def run_publish_pipeline(
    page_name: str,
    publish: bool = True,
    session_id: str | None = None,
) -> str:
    """Publish or unpublish a page.

    Args:
        page_name: Name of the page
        publish: True to publish, False to unpublish
        session_id: Optional session ID for event streaming

    Returns:
        Status message
    """
    action = "Publishing" if publish else "Unpublishing"
    logger.info(f"{action} page '{page_name}'")
    mcp = get_mcp_client()

    # Find the page
    emit_status_sync(session_id, f"Finding '{page_name}'...", "step_start")
    page = await find_page_by_name(page_name)
    if not page:
        return f"ERROR: Could not find page '{page_name}'"

    page_id = page["id"]
    page_title = page["title"]
    emit_status_sync(session_id, f"Found '{page_title}' (ID: {page_id})", "step_complete")

    # Check current state
    is_published = page.get("published", False)
    if is_published == publish:
        state = "published" if publish else "draft"
        return f"INFO: '{page_title}' is already {state}"

    # Update publish state
    emit_status_sync(session_id, f"{action}...", "step_start")
    try:
        tool = "publish_page" if publish else "unpublish_page"
        await mcp.call_tool(tool, {"page_id": page_id})

        state = "published" if publish else "draft"
        msg = f"SUCCESS: '{page_title}' is now {state}"
        emit_status_sync(session_id, msg, "pipeline_complete")
        return msg

    except Exception as e:
        msg = f"ERROR: Failed to {action.lower()} page: {e}"
        emit_status_sync(session_id, msg, "pipeline_error")
        return msg


async def publish_page(page_name: str, session_id: str | None = None) -> str:
    """Publish a draft page to make it live on the website."""
    return await run_publish_pipeline(page_name, publish=True, session_id=session_id)


async def unpublish_page(page_name: str, session_id: str | None = None) -> str:
    """Unpublish a page, reverting it to draft status."""
    return await run_publish_pipeline(page_name, publish=False, session_id=session_id)


publish_pipeline_tool = FunctionTool(func=publish_page)

unpublish_pipeline_tool = FunctionTool(func=unpublish_page)


# =============================================================================
# Update Content Pipeline
# =============================================================================


async def update_page_content(
    page_name: str,
    block_name: str,
    block_content: str,
    session_id: str | None = None,
) -> str:
    """Update a single content block on a page.

    Args:
        page_name: Name of the page to update
        block_name: Name of the block to update (e.g., 'cjBlockHero')
        block_content: HTML content for the block
        session_id: Optional session ID for event streaming

    Returns:
        Status message
    """
    logger.info(f"Updating content for '{page_name}'")
    mcp = get_mcp_client()

    # Find the page
    emit_status_sync(session_id, f"Finding '{page_name}'...", "step_start")
    page = await find_page_by_name(page_name)
    if not page:
        return f"ERROR: Could not find page '{page_name}'"

    page_id = page["id"]
    page_title = page["title"]
    emit_status_sync(session_id, f"Found '{page_title}' (ID: {page_id})", "step_complete")

    # Update block
    emit_status_sync(session_id, f"Updating block '{block_name}'...", "step_start")
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
        emit_status_sync(session_id, msg, "pipeline_complete")
        return msg

    except Exception as e:
        msg = f"ERROR: Failed to update content: {e}"
        emit_status_sync(session_id, msg, "pipeline_error")
        return msg


update_content_pipeline_tool = FunctionTool(func=update_page_content)


# =============================================================================
# Search/List Pipelines
# =============================================================================


async def search_pages(
    query: str | None = None,
    parent_name: str | None = None,
    session_id: str | None = None,
) -> str:
    """Search for pages by keyword or filter by parent category.

    Args:
        query: Optional search term
        parent_name: Optional parent page name to filter by
        session_id: Optional session ID for event streaming

    Returns:
        Formatted list of matching pages
    """
    logger.info(f"Searching pages: query='{query}', parent='{parent_name}'")
    mcp = get_mcp_client()

    emit_status_sync(session_id, "Searching...", "step_start")

    try:
        params: dict[str, Any] = {}
        if query:
            params["search"] = query
        if parent_name:
            # Find parent ID first
            parent = await find_page_by_name(parent_name)
            if parent:
                params["parent_id"] = str(parent["id"])

        pages = await mcp.call_tool("list_pages", params)

        if not pages:
            return "No pages found matching your criteria."

        # Format results
        lines = [f"Found {len(pages)} page(s):"]
        for page in pages:
            status = "published" if page.get("published") else "draft"
            lines.append(f"  - {page['title']} (ID: {page['id']}, {status})")

        msg = "\n".join(lines)
        emit_status_sync(session_id, f"Found {len(pages)} pages", "pipeline_complete")
        return msg

    except Exception as e:
        msg = f"ERROR: Search failed: {e}"
        emit_status_sync(session_id, msg, "pipeline_error")
        return msg


search_pipeline_tool = FunctionTool(func=search_pages)


async def list_pages(
    parent_name: str | None = None,
    session_id: str | None = None,
) -> str:
    """List all pages or pages under a specific parent category.

    Args:
        parent_name: Optional parent to list children of
        session_id: Optional session ID for event streaming

    Returns:
        Formatted list of pages
    """
    return await search_pages(query=None, parent_name=parent_name, session_id=session_id)


list_pipeline_tool = FunctionTool(func=list_pages)


async def get_page_details(
    page_name: str,
    session_id: str | None = None,
) -> str:
    """Get detailed information about a specific page including blocks and metadata.

    Args:
        page_name: Name of the page to get
        session_id: Optional session ID for event streaming

    Returns:
        Formatted page details
    """
    logger.info(f"Getting details for '{page_name}'")
    mcp = get_mcp_client()

    emit_status_sync(session_id, f"Finding '{page_name}'...", "step_start")
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
            lines.append(f"Blocks ({len(blocks)}): {', '.join(b.get('name', '?') for b in blocks)}")

        msg = "\n".join(lines)
        emit_status_sync(session_id, "Details retrieved", "pipeline_complete")
        return msg

    except Exception as e:
        msg = f"ERROR: Failed to get page details: {e}"
        emit_status_sync(session_id, msg, "pipeline_error")
        return msg


get_page_pipeline_tool = FunctionTool(func=get_page_details)


# Export all tools
__all__ = [
    "move_pipeline_tool",
    "delete_pipeline_tool",
    "publish_pipeline_tool",
    "unpublish_pipeline_tool",
    "update_content_pipeline_tool",
    "search_pipeline_tool",
    "list_pipeline_tool",
    "get_page_pipeline_tool",
    "find_page_by_name",
]
