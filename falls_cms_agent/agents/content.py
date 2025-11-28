"""Content Agent - transforms research into engaging content with brand voice."""

from google.adk.agents import LlmAgent

from ..common.schemas import WaterfallPageDraft
from ..core.callbacks import content_callback
from ..core.config import Config
from ..core.prompts import load_prompt


def create_content_agent() -> LlmAgent:
    """Create the content agent for voice/tone transformation.

    This agent takes research results and transforms them into
    engaging content that matches the Falls Into Love brand voice.

    No tools needed - this is pure LLM reasoning with specific
    voice/tone instructions.

    Output is validated against WaterfallPageDraft schema.
    """
    return LlmAgent(
        name="content_agent",
        model=Config.CONTENT_MODEL,
        description="Transforms research data into engaging content with the Falls Into Love brand voice.",
        instruction=load_prompt("content"),
        tools=[],  # No tools - pure content generation
        output_schema=WaterfallPageDraft,
        output_key="crafted_content",
        before_agent_callback=content_callback,
    )


# Create the agent instance
content_agent = create_content_agent()
