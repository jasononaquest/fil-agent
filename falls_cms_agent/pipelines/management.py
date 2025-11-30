"""Page Management Pipelines - tools for move, delete, publish, and update operations.

These are simpler pipelines that don't require research or content generation.
They interact directly with the CMS via the MCP SDK client.
"""

import re
from typing import Any

from google.adk.tools import FunctionTool, ToolContext

from ..common.schemas import Category, ContentBlock, PageListResult, PageSummary
from ..core.callbacks import emit_status
from ..core.context import set_user_id
from ..core.logging import get_logger
from ..core.mcp_client import get_mcp_client

logger = get_logger(__name__)


def _init_user_context(tool_context: ToolContext | None) -> None:
    """Extract user_id from ToolContext and set in ContextVar for event streaming.

    ADK injects ToolContext with user_id as a direct attribute.
    We store it in a ContextVar so await emit_status() can access it.
    """
    if tool_context and hasattr(tool_context, "user_id") and tool_context.user_id:
        set_user_id(tool_context.user_id)
        logger.debug(f"Set user_id={tool_context.user_id} from ToolContext")


def _normalize_page_name(page_name: str) -> str:
    """Normalize a page name by stripping common suffixes.

    Users often say "the Multnomah Falls page" when they mean "Multnomah Falls".
    This strips those suffixes for better matching.

    Args:
        page_name: Raw page name from user input

    Returns:
        Normalized page name with suffixes stripped
    """
    normalized = page_name.strip()

    # Strip common suffixes (case-insensitive)
    suffixes = [" page", " article", " post"]
    lower = normalized.lower()
    for suffix in suffixes:
        if lower.endswith(suffix):
            normalized = normalized[: -len(suffix)].strip()
            break

    # Also strip leading "the "
    if normalized.lower().startswith("the "):
        normalized = normalized[4:].strip()

    return normalized


async def _search_pages_by_name(page_name: str) -> tuple[list, str]:
    """Search for pages matching a name. Shared helper for find functions.

    Args:
        page_name: Name/title or slug to search for

    Returns:
        Tuple of (list of matching pages, lowercased search term)
    """
    # Normalize the name first (strip "page" suffix, etc.)
    normalized = _normalize_page_name(page_name)
    logger.debug(f"Normalized '{page_name}' to '{normalized}'")

    mcp = get_mcp_client()
    pages = await mcp.call_tool("list_pages", {"search": normalized})
    return (pages if isinstance(pages, list) else [], normalized.lower())


def _find_exact_match(pages: list, search_lower: str) -> dict | None:
    """Find exact title or slug match from a list of pages.

    Args:
        pages: List of page dicts from API
        search_lower: Lowercased search term

    Returns:
        Page dict if exact match found, None otherwise
    """
    # Try exact title match first
    for page in pages:
        if page.get("title", "").lower() == search_lower:
            return page

    # Try exact slug match (for inputs like "butte-falls-oregon-1")
    for page in pages:
        if page.get("slug", "").lower() == search_lower:
            return page

    return None


async def find_page_by_name(page_name: str) -> dict | None:
    """Find a page by name or slug, with fuzzy fallback.

    Use this when looking for a waterfall/content page to operate on.
    Tries exact match first, falls back to first search result.

    This is helpful when users use shorthand names like "La Fortuna"
    for a page titled "La Fortuna, Costa Rica".

    Args:
        page_name: Name/title or slug of the page to find

    Returns:
        Page dict if found (exact or fuzzy), None if no results
    """
    try:
        pages, search_lower = await _search_pages_by_name(page_name)

        if not pages:
            return None

        # Try exact match first
        exact = _find_exact_match(pages, search_lower)
        if exact:
            return exact

        # Fall back to first result (fuzzy match)
        logger.debug(
            f"No exact match for '{page_name}', using first result: '{pages[0].get('title')}'"
        )
        return pages[0]

    except Exception as e:
        logger.warning(f"Error finding page '{page_name}': {e}")
        return None


async def find_category_by_name(category_name: str) -> Category | None:
    """Find a category by exact name or slug match only.

    Use this when looking for a category/parent page. Does NOT return
    partial matches - this prevents confusion between "Costa Rica" (category)
    and "La Fortuna, Costa Rica" (waterfall page).

    The input is normalized before searching, so "costa rica" will find "Costa Rica".

    Args:
        category_name: Name/title or slug of the category (will be normalized)

    Returns:
        Category object if exact match found, None otherwise
    """
    try:
        # Normalize the search term first
        normalized = Category(title=category_name)
        pages, search_lower = await _search_pages_by_name(normalized.title)

        if not pages:
            return None

        # Only return exact matches
        exact = _find_exact_match(pages, search_lower)
        if exact:
            return Category.from_api_response(exact)

        # Log similar pages for debugging but don't return them
        logger.debug(
            f"No exact category match for '{normalized.title}'. "
            f"Similar pages: {[p.get('title') for p in pages[:3]]}"
        )
        return None

    except Exception as e:
        logger.warning(f"Error finding category '{category_name}': {e}")
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

    The category name is automatically normalized (e.g., "costa rica" -> "Costa Rica").

    Args:
        category_name: Name of the category (e.g., "Oregon", "Mount Rainier")
        parent_name: Optional parent category to nest under
        tool_context: Injected by ADK - contains user_id for event streaming

    Returns:
        Status message with the created category ID
    """
    _init_user_context(tool_context)

    # Create Category model - this normalizes the name automatically
    category = Category(title=category_name)
    logger.info(f"Creating category '{category.title}' (input was '{category_name}')")
    mcp = get_mcp_client()

    # Check if category already exists (strict match)
    await emit_status(f"Checking if '{category.title}' exists...", "step_start")
    existing = await find_category_by_name(category.title)
    if existing:
        return f"INFO: Category '{existing.title}' already exists (ID: {existing.id})"
    await emit_status("Category doesn't exist yet", "step_complete")

    # Find parent if specified (strict match for parent categories)
    parent: Category | None = None
    if parent_name:
        await emit_status(f"Finding parent '{parent_name}'...", "step_start")
        parent = await find_category_by_name(parent_name)
        if not parent:
            # Normalize the parent name for the error message
            normalized_parent = Category(title=parent_name)
            return f"ERROR: Could not find parent category '{normalized_parent.title}'. Create it first."
        category.parent_id = parent.id
        await emit_status(f"Found parent '{parent.title}' (ID: {parent.id})", "step_complete")

    # Create the category
    await emit_status(f"Creating category '{category.title}'...", "step_start")
    try:
        created = await mcp.call_tool("create_category_page", category.to_mcp_dict())
        category_id = created.get("id") if isinstance(created, dict) else None

        if category_id:
            parent_info = f" under '{parent.title}'" if parent else ""
            msg = f"SUCCESS: Created category '{category.title}' (ID: {category_id}){parent_info}"
            await emit_status(msg, "pipeline_complete")
            return msg
        else:
            msg = f"ERROR: Failed to create category '{category.title}'"
            await emit_status(msg, "pipeline_error")
            return msg

    except Exception as e:
        msg = f"ERROR: Failed to create category: {e}"
        await emit_status(msg, "pipeline_error")
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
    await emit_status(f"Finding '{page_name}'...", "step_start")
    page = await find_page_by_name(page_name)
    if not page:
        return f"ERROR: Could not find page '{page_name}'"

    page_id = page["id"]
    await emit_status(f"Found page (ID: {page_id})", "step_complete")

    # Find the new parent (strict match - must be exact category name)
    parent: Category | None = None
    if new_parent_name:
        await emit_status(f"Finding parent '{new_parent_name}'...", "step_start")
        parent = await find_category_by_name(new_parent_name)
        if not parent:
            # Normalize for clearer error message
            normalized = Category(title=new_parent_name)
            return f"ERROR: Could not find parent category '{normalized.title}'. Create it first with create_category_page."
        await emit_status(f"Found parent '{parent.title}' (ID: {parent.id})", "step_complete")

    # Execute the move
    await emit_status("Moving page...", "step_start")
    try:
        await mcp.call_tool(
            "move_page",
            {
                "page_id": page_id,
                "new_parent_id": parent.id if parent else None,
            },
        )

        dest = f"under '{parent.title}'" if parent else "to root level"
        msg = f"SUCCESS: Moved '{page['title']}' {dest}"
        await emit_status(msg, "pipeline_complete")
        return msg

    except Exception as e:
        msg = f"ERROR: Failed to move page: {e}"
        await emit_status(msg, "pipeline_error")
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
    await emit_status(f"Finding '{page_name}'...", "step_start")
    page = await find_page_by_name(page_name)
    if not page:
        return f"ERROR: Could not find page '{page_name}'"

    page_id = page["id"]
    page_title = page["title"]
    await emit_status(f"Found '{page_title}' (ID: {page_id})", "step_complete")

    # Check current state
    is_published = page.get("published", False)
    if is_published == publish:
        state = "published" if publish else "draft"
        return f"INFO: '{page_title}' is already {state}"

    # Update publish state
    await emit_status(f"{action}...", "step_start")
    try:
        tool = "publish_page" if publish else "unpublish_page"
        await mcp.call_tool(tool, {"page_id": page_id})

        state = "published" if publish else "draft"
        msg = f"SUCCESS: '{page_title}' is now {state}"
        await emit_status(msg, "pipeline_complete")
        return msg

    except Exception as e:
        msg = f"ERROR: Failed to {action.lower()} page: {e}"
        await emit_status(msg, "pipeline_error")
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
# Nav Location Management
# =============================================================================


async def _find_nav_location_by_name(nav_name: str) -> dict | None:
    """Find a nav location by name (case-insensitive).

    Args:
        nav_name: Name of the nav location (e.g., "Primary Nav", "primary", "footer")

    Returns:
        Nav location dict with id and name, or None if not found
    """
    mcp = get_mcp_client()
    try:
        locations = await mcp.call_tool("list_nav_locations", {})
        if not locations:
            return None

        # Normalize search term
        search_lower = nav_name.lower().strip()

        # Try exact match first
        for loc in locations:
            if loc.get("name", "").lower() == search_lower:
                return loc

        # Try partial match (e.g., "primary" -> "Primary Nav", "footer" -> "Footer Nav")
        for loc in locations:
            loc_name_lower = loc.get("name", "").lower()
            if search_lower in loc_name_lower or loc_name_lower in search_lower:
                return loc

        return None

    except Exception as e:
        logger.warning(f"Error finding nav location '{nav_name}': {e}")
        return None


async def _get_available_nav_locations() -> list[str]:
    """Get list of available nav location names for error messages."""
    mcp = get_mcp_client()
    try:
        locations = await mcp.call_tool("list_nav_locations", {})
        return [loc.get("name", "") for loc in (locations or [])]
    except Exception:
        return []


async def add_to_nav_location(
    page_name: str,
    nav_location_name: str,
    tool_context: ToolContext | None = None,
) -> str:
    """Add a page to a navigation location (e.g., Primary Nav, Footer Nav).

    Args:
        page_name: Name of the page to add
        nav_location_name: Name of the nav location (e.g., "Primary Nav")
        tool_context: Injected by ADK - contains user_id for event streaming

    Returns:
        Status message
    """
    _init_user_context(tool_context)
    logger.info(f"Adding '{page_name}' to nav location '{nav_location_name}'")
    mcp = get_mcp_client()

    # Find the page
    await emit_status(f"Finding '{page_name}'...", "step_start")
    page = await find_page_by_name(page_name)
    if not page:
        return f"ERROR: Could not find page '{page_name}'"

    page_id = page["id"]
    page_title = page["title"]
    await emit_status(f"Found '{page_title}' (ID: {page_id})", "step_complete")

    # Find the nav location
    await emit_status(f"Finding nav location '{nav_location_name}'...", "step_start")
    nav_location = await _find_nav_location_by_name(nav_location_name)
    if not nav_location:
        available = await _get_available_nav_locations()
        available_str = ", ".join(available) if available else "none found"
        return (
            f"ERROR: Could not find nav location '{nav_location_name}'. Available: {available_str}"
        )

    nav_id = nav_location["id"]
    nav_name = nav_location["name"]
    await emit_status(f"Found '{nav_name}' (ID: {nav_id})", "step_complete")

    # Add to nav location
    await emit_status(f"Adding to {nav_name}...", "step_start")
    try:
        result = await mcp.call_tool(
            "add_page_to_nav_location",
            {"page_id": page_id, "nav_location_id": nav_id},
        )

        message = (
            result.get("message", f"Added to {nav_name}")
            if isinstance(result, dict)
            else f"Added to {nav_name}"
        )
        await emit_status(message, "pipeline_complete")
        return f"SUCCESS: {message}"

    except Exception as e:
        msg = f"ERROR: Failed to add to nav location: {e}"
        await emit_status(msg, "pipeline_error")
        return msg


async def remove_from_nav_location(
    page_name: str,
    nav_location_name: str,
    tool_context: ToolContext | None = None,
) -> str:
    """Remove a page from a navigation location.

    Args:
        page_name: Name of the page to remove
        nav_location_name: Name of the nav location (e.g., "Primary Nav")
        tool_context: Injected by ADK - contains user_id for event streaming

    Returns:
        Status message
    """
    _init_user_context(tool_context)
    logger.info(f"Removing '{page_name}' from nav location '{nav_location_name}'")
    mcp = get_mcp_client()

    # Find the page
    await emit_status(f"Finding '{page_name}'...", "step_start")
    page = await find_page_by_name(page_name)
    if not page:
        return f"ERROR: Could not find page '{page_name}'"

    page_id = page["id"]
    page_title = page["title"]
    await emit_status(f"Found '{page_title}' (ID: {page_id})", "step_complete")

    # Find the nav location
    await emit_status(f"Finding nav location '{nav_location_name}'...", "step_start")
    nav_location = await _find_nav_location_by_name(nav_location_name)
    if not nav_location:
        available = await _get_available_nav_locations()
        available_str = ", ".join(available) if available else "none found"
        return (
            f"ERROR: Could not find nav location '{nav_location_name}'. Available: {available_str}"
        )

    nav_id = nav_location["id"]
    nav_name = nav_location["name"]
    await emit_status(f"Found '{nav_name}' (ID: {nav_id})", "step_complete")

    # Remove from nav location
    await emit_status(f"Removing from {nav_name}...", "step_start")
    try:
        result = await mcp.call_tool(
            "remove_page_from_nav_location",
            {"page_id": page_id, "nav_location_id": nav_id},
        )

        message = (
            result.get("message", f"Removed from {nav_name}")
            if isinstance(result, dict)
            else f"Removed from {nav_name}"
        )
        await emit_status(message, "pipeline_complete")
        return f"SUCCESS: {message}"

    except Exception as e:
        msg = f"ERROR: Failed to remove from nav location: {e}"
        await emit_status(msg, "pipeline_error")
        return msg


add_to_nav_pipeline_tool = FunctionTool(func=add_to_nav_location)

remove_from_nav_pipeline_tool = FunctionTool(func=remove_from_nav_location)


# =============================================================================
# Rename Page Pipeline
# =============================================================================


async def rename_page(
    page_name: str,
    new_name: str,
    tool_context: ToolContext | None = None,
) -> str:
    """Rename a page by changing its title.

    This updates only the title (and optionally regenerates the slug).
    It does NOT change the page content - use update_page_content for that.

    Args:
        page_name: Current name of the page to rename
        new_name: New title for the page
        tool_context: Injected by ADK - contains user_id for event streaming

    Returns:
        Status message
    """
    _init_user_context(tool_context)
    logger.info(f"Renaming page '{page_name}' to '{new_name}'")
    mcp = get_mcp_client()

    # Validate new name isn't empty
    new_name = new_name.strip()
    if not new_name:
        return "ERROR: New name cannot be empty"

    # Find the page to rename
    await emit_status(f"Finding '{page_name}'...", "step_start")
    page = await find_page_by_name(page_name)
    if not page:
        return f"ERROR: Could not find page '{page_name}'"

    page_id = page["id"]
    old_title = page["title"]
    await emit_status(f"Found '{old_title}' (ID: {page_id})", "step_complete")

    # Check if name is actually changing
    if old_title.lower() == new_name.lower():
        return f"INFO: Page is already named '{old_title}'"

    # Rename the page
    await emit_status(f"Renaming to '{new_name}'...", "step_start")
    try:
        await mcp.call_tool(
            "update_page_metadata",
            {
                "page_id": page_id,
                "title": new_name,
            },
        )

        msg = f"SUCCESS: Renamed '{old_title}' to '{new_name}'"
        await emit_status(msg, "pipeline_complete")
        return msg

    except Exception as e:
        msg = f"ERROR: Failed to rename page: {e}"
        await emit_status(msg, "pipeline_error")
        return msg


rename_pipeline_tool = FunctionTool(func=rename_page)


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
    await emit_status(f"Finding '{page_name}'...", "step_start")
    page = await find_page_by_name(page_name)
    if not page:
        return f"ERROR: Could not find page '{page_name}'"

    page_id = page["id"]
    page_title = page["title"]
    await emit_status(f"Found '{page_title}' (ID: {page_id})", "step_complete")

    # Update block
    await emit_status(f"Updating block '{block_name}'...", "step_start")
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
        await emit_status(msg, "pipeline_complete")
        return msg

    except Exception as e:
        msg = f"ERROR: Failed to update content: {e}"
        await emit_status(msg, "pipeline_error")
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

    await emit_status("Searching...", "step_start")

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
            await emit_status("No pages found", "pipeline_complete")
            return PageListResult.create(pages=[], filter_applied=filter_applied).model_dump()

        # Parse into structured PageSummary objects
        pages = [PageSummary.from_api_dict(p) for p in raw_pages]

        await emit_status(f"Found {len(pages)} pages", "pipeline_complete")
        return PageListResult.create(
            pages=pages,
            filter_applied=filter_applied,
        ).model_dump()

    except Exception as e:
        msg = f"ERROR: Search failed: {e}"
        await emit_status(msg, "pipeline_error")
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

    await emit_status(f"Finding '{page_name}'...", "step_start")
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
        await emit_status("Details retrieved", "pipeline_complete")
        return msg

    except Exception as e:
        msg = f"ERROR: Failed to get page details: {e}"
        await emit_status(msg, "pipeline_error")
        return msg


get_page_pipeline_tool = FunctionTool(func=get_page_details)


# Export all tools
__all__ = [
    "create_category_pipeline_tool",
    "move_pipeline_tool",
    "rename_pipeline_tool",
    "publish_pipeline_tool",
    "unpublish_pipeline_tool",
    "add_to_nav_pipeline_tool",
    "remove_from_nav_pipeline_tool",
    "update_content_pipeline_tool",
    "search_pipeline_tool",
    "list_pipeline_tool",
    "get_page_pipeline_tool",
    "find_page_by_name",
    "find_category_by_name",
]
