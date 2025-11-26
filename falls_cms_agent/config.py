"""Configuration and environment loading for the agent."""

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
    """Agent configuration from environment variables."""

    # Google AI / Vertex AI
    USE_VERTEX_AI: bool = os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "FALSE").upper() == "TRUE"
    GOOGLE_API_KEY: str | None = os.getenv("GOOGLE_API_KEY")
    GOOGLE_CLOUD_PROJECT: str | None = os.getenv("GOOGLE_CLOUD_PROJECT")
    GOOGLE_CLOUD_LOCATION: str | None = os.getenv("GOOGLE_CLOUD_LOCATION", "us-west1")

    # MCP Server
    MCP_SERVER_URL: str = os.getenv("MCP_SERVER_URL", "http://localhost:8000/sse")
    MCP_API_KEY: str | None = os.getenv("MCP_API_KEY")

    # Model configuration
    DEFAULT_MODEL: str = "gemini-2.0-flash"

    @classmethod
    def get_mcp_headers(cls) -> dict[str, str] | None:
        """Get headers for MCP server connection."""
        if cls.MCP_API_KEY:
            return {"Authorization": f"Bearer {cls.MCP_API_KEY}"}
        return None

    @classmethod
    def validate(cls) -> None:
        """Validate required configuration is present."""
        if not cls.USE_VERTEX_AI and not cls.GOOGLE_API_KEY:
            raise ValueError(
                "GOOGLE_API_KEY is required when GOOGLE_GENAI_USE_VERTEXAI is FALSE"
            )
        if cls.USE_VERTEX_AI and not cls.GOOGLE_CLOUD_PROJECT:
            raise ValueError(
                "GOOGLE_CLOUD_PROJECT is required when GOOGLE_GENAI_USE_VERTEXAI is TRUE"
            )


# Validate on import (will raise if misconfigured)
# Commented out for now to allow imports without .env during development
# Config.validate()
