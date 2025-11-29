"""Context management for request-scoped data.

Uses ContextVars to "teleport" request-scoped data (like user_id) into deep
pipeline functions without cluttering every function signature.

This is thread-safe and async-safe - each request gets its own isolated context.
"""

import threading
from contextvars import ContextVar

from .logging import get_logger

logger = get_logger(__name__)

# User ID for the current request - used for event streaming to Rails
current_user_id: ContextVar[int | str | None] = ContextVar("user_id", default=None)


def get_user_id() -> int | str | None:
    """Get the user_id for the current execution context."""
    value = current_user_id.get()
    thread_id = threading.current_thread().ident
    logger.debug(f"[CONTEXT] get_user_id() -> {value} (thread={thread_id})")
    return value


def set_user_id(user_id: int | str | None) -> None:
    """Set the user_id at the start of the request."""
    thread_id = threading.current_thread().ident
    logger.info(f"[CONTEXT] set_user_id({user_id}) (thread={thread_id})")
    current_user_id.set(user_id)
