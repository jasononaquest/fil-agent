"""Research Agent - searches the web for waterfall information."""

from google.adk.agents import LlmAgent
from google.adk.tools import google_search

from ..callbacks import research_callback
from ..config import Config
from ..prompts.research import RESEARCH_INSTRUCTION


def create_research_agent() -> LlmAgent:
    """Create the research agent with Google Search tool.

    This agent searches the web for factual waterfall and
    hiking trail information.

    Note: google_search is a built-in tool that only works with
    Gemini 2 models. Due to ADK's single built-in tool limitation,
    this agent cannot have other tools.
    """
    return LlmAgent(
        name="research_agent",
        model=Config.DEFAULT_MODEL,
        description="Searches the web for waterfall and hiking trail information using Google Search.",
        instruction=RESEARCH_INSTRUCTION,
        tools=[google_search],
        output_key="research_results",
        before_agent_callback=research_callback,
    )


# Create the agent instance
research_agent = create_research_agent()
