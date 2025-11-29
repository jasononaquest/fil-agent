"""Callbacks for agent events and HTTP push to Rails.

Uses ContextVars to get user_id without requiring it as a parameter.
This allows emit_status_sync() to be called from deep in the pipeline
without threading user_id through every function signature.
"""

import asyncio
from collections.abc import Callable
from typing import Any

import httpx

from .config import Config
from .context import get_user_id
from .logging import get_logger

logger = get_logger(__name__)


async def emit_status(
    message: str,
    event_type: str = "step",
    extra_data: dict[str, Any] | None = None,
    user_id: int | str | None = None,
) -> None:
    """Push a status event to Rails via HTTP.

    This is fire-and-forget - we never want to crash the agent
    due to a UI communication failure.

    Args:
        message: Human-readable status message
        event_type: Type of event (step, step_complete, error, etc.)
        extra_data: Additional data to include in the payload
        user_id: Optional override - if not provided, reads from ContextVar
    """
    logger.info(f"[EMIT] emit_status called: event_type={event_type}, message={message}")

    # Use provided user_id or fall back to ContextVar
    uid = user_id if user_id is not None else get_user_id()
    logger.info(f"[EMIT] user_id: provided={user_id}, from_context={get_user_id()}, using={uid}")

    if not Config.events_enabled():
        logger.warning(
            f"[EMIT] SKIPPED (events not configured): {event_type} - {message}. "
            f"RAILS_EVENTS_URL={Config.RAILS_EVENTS_URL}"
        )
        return

    if not uid:
        logger.warning(f"[EMIT] SKIPPED (no user_id): {event_type} - {message}")
        return

    payload = {
        "user_id": uid,
        "event_type": event_type,
        "payload": {
            "content": message,
            **(extra_data or {}),
        },
    }

    url = Config.RAILS_EVENTS_URL
    headers = Config.get_rails_headers()
    logger.info(f"[EMIT] POSTing to {url}")
    logger.info(f"[EMIT] Headers: {list(headers.keys())}")
    logger.info(f"[EMIT] Payload: {payload}")

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                json=payload,
                headers=headers,
                timeout=2.0,  # Short timeout - don't block agent
            )
            logger.info(
                f"[EMIT] Response: status={response.status_code}, body={response.text[:200]}"
            )
            if response.status_code != 200:
                logger.warning(f"[EMIT] Event push failed: status={response.status_code}")
    except httpx.TimeoutException:
        logger.warning("[EMIT] Event push timed out (continuing)")
    except Exception as e:
        logger.warning(f"[EMIT] Event push exception: {type(e).__name__}: {e}")


def emit_status_sync(
    message: str,
    event_type: str = "step",
    extra_data: dict[str, Any] | None = None,
) -> None:
    """Synchronous wrapper for emit_status.

    Use this in non-async contexts. Reads user_id from ContextVar.
    """
    logger.info(f"[EMIT_SYNC] emit_status_sync called: {event_type} - {message}")
    try:
        loop = asyncio.get_event_loop()
        logger.info(f"[EMIT_SYNC] Got event loop, is_running={loop.is_running()}")
        if loop.is_running():
            # Schedule the coroutine to run
            logger.info("[EMIT_SYNC] Loop running, creating task")
            asyncio.create_task(emit_status(message, event_type, extra_data))
        else:
            logger.info("[EMIT_SYNC] Loop not running, using run_until_complete")
            loop.run_until_complete(emit_status(message, event_type, extra_data))
    except RuntimeError as e:
        # No event loop - create one
        logger.info(f"[EMIT_SYNC] RuntimeError ({e}), using asyncio.run")
        asyncio.run(emit_status(message, event_type, extra_data))


def create_step_callback(step_name: str) -> Callable:
    """Create an ADK before_agent_callback that emits step status.

    Reads user_id from ContextVar automatically.

    Args:
        step_name: Human-readable name for this step (e.g., "Researching")

    Returns:
        A callback function compatible with ADK's before_agent_callback
    """

    def callback(callback_context: Any) -> None:
        emit_status_sync(f"{step_name}...", "step_start")
        logger.info(f"Starting step: {step_name}", extra={"step": step_name})

    return callback


def create_complete_callback(step_name: str) -> Callable:
    """Create an ADK after_agent_callback that emits step completion.

    Reads user_id from ContextVar automatically.

    Args:
        step_name: Human-readable name for this step

    Returns:
        A callback function compatible with ADK's after_agent_callback
    """

    def callback(callback_context: Any) -> None:
        emit_status_sync(f"{step_name} complete", "step_complete")
        logger.info(f"Completed step: {step_name}", extra={"step": step_name})

    return callback


# Pre-built callbacks for common steps
def check_existing_callback(callback_context: Any) -> None:
    """Callback for the duplicate check step."""
    create_step_callback("Checking for existing pages")(callback_context)


def research_callback(callback_context: Any) -> None:
    """Callback for the research step."""
    create_step_callback("Researching waterfall")(callback_context)


def content_callback(callback_context: Any) -> None:
    """Callback for the content generation step."""
    create_step_callback("Writing content")(callback_context)


def create_in_cms_callback(callback_context: Any) -> None:
    """Callback for the CMS creation step."""
    create_step_callback("Creating page in CMS")(callback_context)
