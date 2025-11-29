"""Dedicated MCP client for calling tools programmatically from Python code.

This uses the actual mcp Python SDK to connect to the MCP server,
NOT the ADK's McpToolset which is designed for LLM tool descriptions.

Reference: https://modelcontextprotocol.io/docs/tools
"""

import json
from contextlib import asynccontextmanager
from typing import Any

from mcp import ClientSession
from mcp.client.sse import sse_client

from .config import Config
from .logging import get_logger

logger = get_logger(__name__)


class McpClient:
    """Client for calling MCP tools programmatically.

    Uses the mcp SDK's ClientSession for actual tool execution,
    connecting via SSE transport to the MCP server.
    """

    def __init__(self):
        self.server_url = Config.MCP_SERVER_URL
        if not self.server_url:
            raise ValueError("MCP_SERVER_URL is required")

    def _get_headers(self) -> dict[str, str]:
        """Get authorization headers for MCP server."""
        return Config.get_mcp_headers()

    @asynccontextmanager
    async def connect(self):
        """Connect to the MCP server via SSE.

        Yields:
            ClientSession: An initialized MCP session ready for tool calls.
        """
        headers = self._get_headers()
        logger.debug(f"Connecting to MCP server: {self.server_url}")

        async with sse_client(
            url=self.server_url,
            headers=headers,
            timeout=60.0,  # Allow time for complex operations
        ) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                logger.debug("MCP session initialized")
                yield session

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        """Call an MCP tool by name.

        Args:
            tool_name: Name of the tool to call (e.g., "list_pages", "create_page")
            arguments: Tool arguments as a dictionary

        Returns:
            Structured content (dict/list) from Pydantic models, or parsed JSON/text fallback

        Raises:
            Exception: If tool execution fails
        """
        logger.info(f"Calling MCP tool: {tool_name} with args: {arguments}")

        async with self.connect() as session:
            result = await session.call_tool(tool_name, arguments)

            logger.info(
                f"MCP result - isError: {result.isError}, has structuredContent: {result.structuredContent is not None}, content count: {len(result.content) if result.content else 0}"
            )

            # Prefer structuredContent when available (FastMCP returns this for Pydantic models)
            # This is already a Python dict/list, ready to use
            if result.structuredContent is not None:
                content = result.structuredContent
                # FastMCP wraps list returns in {"result": [...]} for JSON schema compliance
                # Unwrap if present
                if isinstance(content, dict) and "result" in content and len(content) == 1:
                    content = content["result"]
                logger.info(f"MCP tool returned structured content: {type(content)}")
                return content

            # Fallback to traditional content (text blocks)
            if result.content:
                content_block = result.content[0]
                logger.info(
                    f"MCP content block type: {type(content_block)}, has text attr: {hasattr(content_block, 'text')}"
                )

                if hasattr(content_block, "text"):
                    text = content_block.text
                    logger.info(f"MCP tool result (text): {text[:500]}...")

                    # Try to parse as JSON
                    try:
                        parsed = json.loads(text)
                        logger.info(f"Parsed JSON type: {type(parsed)}")
                        return parsed
                    except json.JSONDecodeError:
                        logger.warning("Failed to parse as JSON, returning raw text")
                        return text
                else:
                    logger.warning(f"Content block has no text attribute: {content_block}")

            logger.warning("MCP tool returned no content")
            return None

    async def list_tools(self) -> list[str]:
        """List available tools from the MCP server.

        Returns:
            List of tool names
        """
        async with self.connect() as session:
            tools = await session.list_tools()
            return [tool.name for tool in tools.tools]


# Module-level client instance (created on first use)
_client: McpClient | None = None


def get_mcp_client() -> McpClient:
    """Get or create the MCP client singleton.

    Returns:
        McpClient: The shared client instance
    """
    global _client
    if _client is None:
        _client = McpClient()
    return _client
