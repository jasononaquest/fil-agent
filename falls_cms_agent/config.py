"""Configuration and environment loading for the agent."""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables from .env file
# Try multiple locations for Agent Engine deployment compatibility
_package_dir = Path(__file__).parent
_possible_env_locations = [
    _package_dir / ".env",  # Inside package (if copied there)
    _package_dir.parent / ".env",  # Project root / staging root (/code/.env)
    Path.cwd() / ".env",  # Current working directory
]

_env_loaded = False
for _env_file in _possible_env_locations:
    if _env_file.exists():
        load_dotenv(_env_file)
        _env_loaded = True
        break

if not _env_loaded:
    load_dotenv()  # Fallback to default dotenv behavior


class Config:
    """Agent configuration from environment variables."""

    # Google AI / Vertex AI
    USE_VERTEX_AI: bool = os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "FALSE").upper() == "TRUE"
    GOOGLE_API_KEY: str | None = os.getenv("GOOGLE_API_KEY")
    GOOGLE_CLOUD_PROJECT: str | None = os.getenv("GOOGLE_CLOUD_PROJECT")
    GOOGLE_CLOUD_LOCATION: str | None = os.getenv("GOOGLE_CLOUD_LOCATION", "us-west1")

    # MCP Server - must be set via environment variable
    MCP_SERVER_URL: str | None = os.getenv("MCP_SERVER_URL")
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
        if not cls.MCP_SERVER_URL:
            raise ValueError("MCP_SERVER_URL environment variable is required")
        if not cls.USE_VERTEX_AI and not cls.GOOGLE_API_KEY:
            raise ValueError("GOOGLE_API_KEY is required when GOOGLE_GENAI_USE_VERTEXAI is FALSE")
        if cls.USE_VERTEX_AI and not cls.GOOGLE_CLOUD_PROJECT:
            raise ValueError(
                "GOOGLE_CLOUD_PROJECT is required when GOOGLE_GENAI_USE_VERTEXAI is TRUE"
            )


# Validate on import (will raise if misconfigured)
# Commented out for now to allow imports without .env during development
# Config.validate()
