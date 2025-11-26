"""CMS Agent - manages CMS operations via MCP tools."""

from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import SseConnectionParams

from ..config import Config
from ..prompts.cms import CMS_INSTRUCTION


def create_cms_agent() -> LlmAgent:
    """Create the CMS agent with MCP toolset.

    The MCP toolset connects to the Falls Into Love MCP server
    which provides tools for managing CMS content.
    """
    # Build MCP connection parameters
    connection_params = SseConnectionParams(
        url=Config.MCP_SERVER_URL,
        headers=Config.get_mcp_headers(),
    )

    # Create MCP toolset - this discovers tools from the MCP server
    mcp_toolset = McpToolset(connection_params=connection_params)

    return LlmAgent(
        name="cms_agent",
        model=Config.DEFAULT_MODEL,
        description="Manages CMS operations: list, create, update, and delete pages via MCP tools.",
        instruction=CMS_INSTRUCTION,
        tools=[mcp_toolset],
        output_key="cms_result",
    )


# Create the agent instance
# Note: For deployment, this must be synchronous (not async)
cms_agent = create_cms_agent()
