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
    logger.info("=" * 60)
    logger.info("[ROUTER] classify_intent CALLED")
    logger.info(f"[ROUTER] user_request: {user_request}")
    logger.info(f"[ROUTER] tool_context type: {type(tool_context)}")

    # Set user context for event streaming
    user_id = None
    if tool_context:
        if hasattr(tool_context, "user_id"):
            user_id = tool_context.user_id
            logger.info(f"[ROUTER] tool_context.user_id = {user_id}")
        else:
            logger.info(f"[ROUTER] tool_context attrs: {dir(tool_context)}")

        if user_id:
            set_user_id(user_id)
            logger.info(f"[ROUTER] Set user_id={user_id} in ContextVar")
        else:
            logger.warning("[ROUTER] tool_context.user_id is None or missing")
    else:
        logger.warning("[ROUTER] tool_context is None")

    # Load router prompt
    logger.info("[ROUTER] Loading router prompt...")
    router_instruction = load_prompt("router")
    logger.info(f"[ROUTER] Prompt loaded, length={len(router_instruction)} chars")

    # Generate JSON schema from Pydantic model for structured output
    intent_schema = UserIntent.model_json_schema()
    logger.info(
        f"[ROUTER] Generated schema with keys: {list(intent_schema.get('properties', {}).keys())}"
    )

    config = types.GenerateContentConfig(
        system_instruction=router_instruction,
        response_mime_type="application/json",
        response_schema=intent_schema,
    )

    logger.info(f"[ROUTER] Calling model: {Config.ROUTER_MODEL}")
    try:
        response = await _client.aio.models.generate_content(
            model=Config.ROUTER_MODEL,  # Uses Flash for fast classification
            contents=user_request,
            config=config,
        )

        logger.info(f"[ROUTER] Response received, has text: {bool(response.text)}")
        if response.text:
            logger.info(f"[ROUTER] Raw response: {response.text[:500]}")

            # Parse and validate against Pydantic model
            intent = UserIntent.model_validate_json(response.text)
            logger.info("[ROUTER] Parsed intent successfully")
            logger.info(f"[ROUTER] action: {intent.action.value}")
            logger.info(f"[ROUTER] reasoning: {intent.reasoning}")
            logger.info(f"[ROUTER] target_page_name: {intent.target_page_name}")
            logger.info(f"[ROUTER] destination_parent_name: {intent.destination_parent_name}")
            logger.info(f"[ROUTER] search_query: {intent.search_query}")
            logger.info(f"[ROUTER] content_description: {intent.content_description}")

            result = intent.model_dump()
            logger.info(f"[ROUTER] Returning result: {result}")
            logger.info("=" * 60)
            return result
        else:
            logger.warning("[ROUTER] No response text from classification LLM")
            logger.warning(f"[ROUTER] Full response object: {response}")
            fallback = UserIntent(
                reasoning="Could not classify the request",
                action="HELP",
            ).model_dump()
            logger.info(f"[ROUTER] Returning fallback: {fallback}")
            logger.info("=" * 60)
            return fallback

    except Exception as e:
        logger.error(f"[ROUTER] Classification failed with exception: {type(e).__name__}: {e}")
        import traceback

        logger.error(f"[ROUTER] Traceback: {traceback.format_exc()}")
        # Fall back to HELP intent on error
        fallback = UserIntent(
            reasoning=f"Classification error: {e}",
            action="HELP",
        ).model_dump()
        logger.info(f"[ROUTER] Returning error fallback: {fallback}")
        logger.info("=" * 60)
        return fallback


# Wrap as ADK FunctionTool
classify_intent_tool = FunctionTool(func=classify_intent)


__all__ = [
    "classify_intent",
    "classify_intent_tool",
]
