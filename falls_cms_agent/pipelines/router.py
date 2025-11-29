"""Router Pipeline - classifies user intent before dispatching.

This implements the Router/Controller pattern from the Architecture Upgrade Plan.
Uses Gemini Flash (cheap/fast) to classify intent, then the root agent dispatches
to the appropriate pipeline based on the classification.

Benefits:
- Safety: Prevents content hallucination when user just wants to move a page
- Latency: Fast classification with cheap model
- Control: Python code handles edge cases, not LLM probabilistics
"""

from google import genai
from google.adk.tools import FunctionTool, ToolContext
from google.genai import types

from ..common.schemas import UserIntent
from ..core.config import Config
from ..core.context import set_user_id
from ..core.logging import get_logger
from ..core.prompts import load_prompt

logger = get_logger(__name__)

# Initialize genai client
_client = genai.Client()


async def classify_intent(
    user_request: str,
    tool_context: ToolContext | None = None,
) -> dict:
    """Classify the user's request into a structured intent.

    This tool uses Gemini Flash (fast/cheap) to analyze what the user wants
    and returns a structured UserIntent. The root agent should call this
    FIRST before calling any other tools.

    The returned intent includes:
    - action: What type of operation (CREATE_PAGE, MOVE_PAGE, etc.)
    - reasoning: Why this action was chosen
    - target_page_name: The page being acted on
    - destination_parent_name: For move/create operations
    - search_query: For search/list operations
    - content_description: For update operations

    Args:
        user_request: The user's natural language request
        tool_context: Injected by ADK - contains user_id for event streaming

    Returns:
        Dict with classified intent fields. Use the 'action' field to determine
        which pipeline tool to call next.
    """
    logger.info(f"[ROUTER] Classifying intent for: {user_request[:100]}...")

    # Set user context for event streaming
    if tool_context and hasattr(tool_context, "user_id") and tool_context.user_id:
        set_user_id(tool_context.user_id)

    router_instruction = load_prompt("router")

    # Generate JSON schema from Pydantic model for structured output
    intent_schema = UserIntent.model_json_schema()

    config = types.GenerateContentConfig(
        system_instruction=router_instruction,
        response_mime_type="application/json",
        response_schema=intent_schema,
    )

    try:
        response = await _client.aio.models.generate_content(
            model=Config.ROUTER_MODEL,  # Uses Flash for fast classification
            contents=user_request,
            config=config,
        )

        if response.text:
            # Parse and validate against Pydantic model
            intent = UserIntent.model_validate_json(response.text)
            logger.info(f"[ROUTER] Classified as: {intent.action.value} - {intent.reasoning}")
            return intent.model_dump()
        else:
            logger.warning("[ROUTER] No response from classification LLM")
            return UserIntent(
                reasoning="Could not classify the request",
                action="HELP",
            ).model_dump()

    except Exception as e:
        logger.error(f"[ROUTER] Classification failed: {e}")
        # Fall back to HELP intent on error
        return UserIntent(
            reasoning=f"Classification error: {e}",
            action="HELP",
        ).model_dump()


# Wrap as ADK FunctionTool
classify_intent_tool = FunctionTool(func=classify_intent)


__all__ = [
    "classify_intent",
    "classify_intent_tool",
]
