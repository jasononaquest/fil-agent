"""Main agent entry point for Falls Into Love CMS Agent.

This file defines root_agent which is the entry point for ADK.
The agent can be run with: adk web or adk run falls_cms_agent

Architecture:
- root_agent is an LlmAgent with pipeline tools attached
- Each pipeline tool is a FunctionTool that orchestrates sub-agents
- This gives us deterministic control flow (Python code) while staying ADK-compatible
- before_agent_callback captures user_id into ContextVar for event streaming
"""

from google.adk.agents import LlmAgent

from .core.config import Config
from .core.context import set_user_id
from .core.logging import get_logger, setup_logging
from .core.prompts import load_prompt
from .pipelines import ALL_PIPELINE_TOOLS

# Set up logging
setup_logging()

logger = get_logger(__name__)


def capture_user_context(callback_context) -> None:
    """Capture user_id from ADK context and store in ContextVar.

    This runs at the start of each request, before the LLM processes it.
    The user_id is then available to emit_status_sync() via get_user_id().

    ADK passes input parameters in different places depending on the context:
    - callback_context.state: Session state (if sessions are used)
    - callback_context.session.state: Alternative session location
    - callback_context.invocation_context: The original API input
    """
    user_id = None

    # Log what we have to work with
    logger.info(f"Callback context type: {type(callback_context)}")
    logger.info(f"Callback context attrs: {dir(callback_context)}")

    # Check state first (if using session state)
    if hasattr(callback_context, "state") and callback_context.state:
        logger.info(f"callback_context.state: {callback_context.state}")
        user_id = callback_context.state.get("user_id")

    # Check session.state
    if not user_id and hasattr(callback_context, "session"):
        session = callback_context.session
        if session and hasattr(session, "state") and session.state:
            logger.info(f"callback_context.session.state: {session.state}")
            user_id = session.state.get("user_id")

    # Check invocation_context (where API input parameters often are)
    if not user_id and hasattr(callback_context, "invocation_context"):
        inv_ctx = callback_context.invocation_context
        logger.info(f"invocation_context type: {type(inv_ctx)}")
        if hasattr(inv_ctx, "user_id"):
            user_id = inv_ctx.user_id
        elif isinstance(inv_ctx, dict):
            user_id = inv_ctx.get("user_id")

    # Check user_content for input parameters
    if not user_id and hasattr(callback_context, "user_content"):
        logger.info(f"user_content: {callback_context.user_content}")

    if user_id:
        set_user_id(user_id)
        logger.info(f"Context set: user_id={user_id}")
    else:
        logger.warning("No user_id found in callback context - events will be skipped")


# Define the root agent - the main entry point for ADK
root_agent = LlmAgent(
    name="falls_cms_assistant",
    model=Config.DEFAULT_MODEL,
    description="Content assistant for Falls Into Love CMS - creates and manages waterfall pages.",
    instruction=load_prompt("root"),
    tools=ALL_PIPELINE_TOOLS,
    before_agent_callback=capture_user_context,
)
