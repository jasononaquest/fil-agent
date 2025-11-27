"""Configuration and environment loading for the agent."""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables from .env file
# Try multiple locations for Agent Engine deployment compatibility
_package_dir = Path(__file__).parent.parent  # falls_cms_agent/
_possible_env_locations = [
    _package_dir / ".env",  # Inside package (if copied there)
    _package_dir.parent / ".env",  # Project root
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

    # MCP Server
    MCP_SERVER_URL: str | None = os.getenv("MCP_SERVER_URL")
    MCP_API_KEY: str | None = os.getenv("MCP_API_KEY")

    # Rails Event Push (for real-time UI updates)
    RAILS_EVENTS_URL: str | None = os.getenv("RAILS_EVENTS_URL")
    INTERNAL_API_TOKEN: str | None = os.getenv("INTERNAL_API_TOKEN")

    # Model configuration
    ROUTER_MODEL: str = os.getenv("ROUTER_MODEL", "gemini-2.0-flash")  # Fast for classification
    CONTENT_MODEL: str = os.getenv("CONTENT_MODEL", "gemini-2.0-flash")  # For content generation
    DEFAULT_MODEL: str = os.getenv("DEFAULT_MODEL", "gemini-2.0-flash")

    @classmethod
    def get_mcp_headers(cls) -> dict[str, str]:
        """Get headers for MCP server connection.

        Uses OIDC tokens in production (Vertex AI), API key locally.
        """
        if cls.USE_VERTEX_AI and cls.MCP_SERVER_URL:
            # Production: Use OIDC token for Cloud Run authentication
            try:
                from google.auth.transport.requests import Request
                from google.oauth2 import id_token

                # Fetch ID token for the MCP server URL
                token = id_token.fetch_id_token(Request(), cls.MCP_SERVER_URL)
                return {"Authorization": f"Bearer {token}"}
            except Exception:
                # Fall back to API key if OIDC fails
                pass

        # Local development: Use API key
        if cls.MCP_API_KEY:
            return {"Authorization": f"Bearer {cls.MCP_API_KEY}"}

        return {}

    @classmethod
    def get_rails_headers(cls) -> dict[str, str]:
        """Get headers for Rails internal API calls."""
        headers = {"Content-Type": "application/json"}
        if cls.INTERNAL_API_TOKEN:
            headers["X-Internal-Token"] = cls.INTERNAL_API_TOKEN
        return headers

    @classmethod
    def validate(cls) -> None:
        """Validate required configuration is present."""
        errors = []

        if not cls.MCP_SERVER_URL:
            errors.append("MCP_SERVER_URL environment variable is required")

        if not cls.USE_VERTEX_AI and not cls.GOOGLE_API_KEY:
            errors.append("GOOGLE_API_KEY is required when GOOGLE_GENAI_USE_VERTEXAI is FALSE")

        if cls.USE_VERTEX_AI and not cls.GOOGLE_CLOUD_PROJECT:
            errors.append("GOOGLE_CLOUD_PROJECT is required when GOOGLE_GENAI_USE_VERTEXAI is TRUE")

        if errors:
            raise ValueError("\n".join(errors))

    @classmethod
    def is_production(cls) -> bool:
        """Check if running in production (Vertex AI)."""
        return cls.USE_VERTEX_AI

    @classmethod
    def events_enabled(cls) -> bool:
        """Check if event push to Rails is configured."""
        return bool(cls.RAILS_EVENTS_URL and cls.INTERNAL_API_TOKEN)
