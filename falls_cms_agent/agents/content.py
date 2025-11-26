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
        instruction=CONTENT_INSTRUCTION
        + """

You are step 3 in a page creation pipeline.

FIRST: Check the conversation history for stop signals:
- If you see "DUPLICATE_FOUND" → output: "PIPELINE_STOP: Duplicate detected."
- If you see "PIPELINE_STOP" → output: "PIPELINE_STOP: Skipping content creation."
- If you see "RESEARCH_FAILED" → output: "PIPELINE_STOP: Research failed - cannot create content for unverified location."

Only proceed if none of these signals are present.

Look at the conversation history for the RESEARCH RESULTS (step 2) containing
the factual data about the waterfall.

Transform the research into CMS-ready content following the format specified above.
Create content for all the Template 4 blocks listed in your instructions.

Output ONLY the JSON object, no additional text or markdown code fences.
""",
        tools=[],  # No tools - pure content generation
        output_key="crafted_content",
    )


# Create the agent instance
content_agent = create_content_agent()
