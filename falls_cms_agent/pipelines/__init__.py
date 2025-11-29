"""Pipeline tools for multi-step workflows.

Each pipeline is exposed as an ADK FunctionTool that can be used by the root agent.
Pipelines orchestrate sub-agents and MCP tools in Python code, giving us
deterministic control flow while staying ADK-compatible.
"""

from .create_page import (
    create_pipeline_tool,
    create_waterfall_page,
)
from .management import (
    create_category_page,
    create_category_pipeline_tool,
    get_page_details,
    get_page_pipeline_tool,
    list_pages,
    list_pipeline_tool,
    move_page,
    move_pipeline_tool,
    publish_page,
    publish_pipeline_tool,
    search_pages,
    search_pipeline_tool,
    unpublish_page,
    unpublish_pipeline_tool,
    update_content_pipeline_tool,
    update_page_content,
)

# All pipeline tools for easy import
ALL_PIPELINE_TOOLS = [
    create_pipeline_tool,
    create_category_pipeline_tool,
    move_pipeline_tool,
    publish_pipeline_tool,
    unpublish_pipeline_tool,
    update_content_pipeline_tool,
    search_pipeline_tool,
    list_pipeline_tool,
    get_page_pipeline_tool,
]

__all__ = [
    # Create pipelines
    "create_pipeline_tool",
    "create_waterfall_page",
    "create_category_pipeline_tool",
    "create_category_page",
    # Management pipelines
    "move_pipeline_tool",
    "move_page",
    "publish_pipeline_tool",
    "publish_page",
    "unpublish_pipeline_tool",
    "unpublish_page",
    "update_content_pipeline_tool",
    "update_page_content",
    "search_pipeline_tool",
    "search_pages",
    "list_pipeline_tool",
    "list_pages",
    "get_page_pipeline_tool",
    "get_page_details",
    # Convenience export
    "ALL_PIPELINE_TOOLS",
]
