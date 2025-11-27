"""CMS Agent - manages CMS operations via MCP tools.

This agent uses ADK's McpToolset to expose MCP tools to the LLM.
For programmatic MCP access (Python calling tools directly), use
falls_cms_agent.core.mcp_client.get_mcp_client() instead.
"""

from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import SseConnectionParams

from ..core.config import Config
from ..core.prompts import load_prompt


def _create_mcp_toolset() -> McpToolset:
    """Create the MCP toolset for the CMS agent.

    This uses ADK's McpToolset which describes tools to the LLM so it
    can generate JSON tool calls. The ADK handles actual execution.

    Note: This is NOT for direct Python tool calls. Use
    falls_cms_agent.core.mcp_client for that.
    """
    connection_params = SseConnectionParams(
        url=Config.MCP_SERVER_URL,
        headers=Config.get_mcp_headers(),
    )
    return McpToolset(connection_params=connection_params)


def create_cms_agent() -> LlmAgent:
    """Create the CMS agent with MCP toolset.

    The MCP toolset connects to the Falls Into Love MCP server
    which provides tools for managing CMS content.
    """
    return LlmAgent(
        name="cms_agent",
        model=Config.DEFAULT_MODEL,
        description="Manages CMS operations: list, create, update, and delete pages via MCP tools.",
        instruction=load_prompt("cms"),
        tools=[_create_mcp_toolset()],
        output_key="cms_result",
    )


# Create the agent instance
# Note: For deployment, this must be synchronous (not async)
cms_agent = create_cms_agent()
