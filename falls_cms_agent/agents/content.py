"""Content Agent - transforms research into engaging content with brand voice."""

from google.adk.agents import LlmAgent

from ..config import Config
from ..prompts.content import CONTENT_INSTRUCTION


def create_content_agent() -> LlmAgent:
    """Create the content agent for voice/tone transformation.

    This agent takes research results and transforms them into
    engaging content that matches the Falls Into Love brand voice.

    No tools needed - this is pure LLM reasoning with specific
    voice/tone instructions.
    """
    return LlmAgent(
        name="content_agent",
        model=Config.DEFAULT_MODEL,
        description="Transforms research data into engaging content with the Falls Into Love brand voice.",
        instruction=CONTENT_INSTRUCTION + """

Read the research results from {research_results} and transform them into
CMS-ready content following the format specified in your instructions.
""",
        tools=[],  # No tools - pure content generation
        output_key="crafted_content",
    )


# Create the agent instance
content_agent = create_content_agent()
