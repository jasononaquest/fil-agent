"""Callbacks for agent events and HTTP push to Rails."""

import asyncio
from collections.abc import Callable
from typing import Any

import httpx

from .config import Config
from .logging import get_logger

logger = get_logger(__name__)


async def emit_status(
    user_id: int | str | None,
    message: str,
    event_type: str = "step",
    extra_data: dict[str, Any] | None = None,
) -> None:
    """Push a status event to Rails via HTTP.

    This is fire-and-forget - we never want to crash the agent
    due to a UI communication failure.

    Args:
        user_id: The Rails user ID to broadcast to
        message: Human-readable status message
        event_type: Type of event (step, step_complete, error, etc.)
        extra_data: Additional data to include in the payload
    """
    if not Config.events_enabled() or not user_id:
        logger.debug(f"Event skipped (not configured): {event_type} - {message}")
        return

    payload = {
        "user_id": user_id,
        "event_type": event_type,
        "payload": {
            "content": message,
            **(extra_data or {}),
        },
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                Config.RAILS_EVENTS_URL,
                json=payload,
                headers=Config.get_rails_headers(),
                timeout=2.0,  # Short timeout - don't block agent
            )
            if response.status_code != 200:
                logger.warning(f"Event push failed: {response.status_code}")
    except httpx.TimeoutException:
        logger.debug("Event push timed out (continuing)")
    except Exception as e:
        logger.debug(f"Event push failed: {e}")


def emit_status_sync(
    user_id: int | str | None,
    message: str,
    event_type: str = "step",
    extra_data: dict[str, Any] | None = None,
) -> None:
    """Synchronous wrapper for emit_status.

    Use this in non-async contexts (like ADK callbacks).
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Schedule the coroutine to run
            asyncio.create_task(emit_status(user_id, message, event_type, extra_data))
        else:
            loop.run_until_complete(emit_status(user_id, message, event_type, extra_data))
    except RuntimeError:
        # No event loop - create one
        asyncio.run(emit_status(user_id, message, event_type, extra_data))


def create_step_callback(
    step_name: str,
    user_id: int | str | None = None,
) -> Callable:
    """Create an ADK before_agent_callback that emits step status.

    Args:
        step_name: Human-readable name for this step (e.g., "Researching")
        user_id: Rails user ID for event routing

    Returns:
        A callback function compatible with ADK's before_agent_callback
    """

    def callback(callback_context: Any) -> None:
        # Try to get user_id from context if not provided
        uid = user_id
        if uid is None and hasattr(callback_context, "state"):
            uid = callback_context.state.get("user_id")

        emit_status_sync(uid, f"{step_name}...", "step_start")
        logger.info(f"Starting step: {step_name}", extra={"step": step_name})

    return callback


def create_complete_callback(
    step_name: str,
    user_id: int | str | None = None,
) -> Callable:
    """Create an ADK after_agent_callback that emits step completion.

    Args:
        step_name: Human-readable name for this step
        user_id: Rails user ID for event routing

    Returns:
        A callback function compatible with ADK's after_agent_callback
    """

    def callback(callback_context: Any) -> None:
        uid = user_id
        if uid is None and hasattr(callback_context, "state"):
            uid = callback_context.state.get("user_id")

        emit_status_sync(uid, f"{step_name} complete", "step_complete")
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
