"""Callbacks for emitting status updates during agent execution.

These callbacks write to session.state["current_step"] so that external
clients can poll for progress updates during long-running pipelines.
"""

from google.adk.agents.callback_context import CallbackContext
from google.genai import types


def emit_step_status(step_message: str):
    """Factory function to create a before_agent_callback that emits a status message.

    Args:
        step_message: Human-friendly message describing what this step is doing.

    Returns:
        A callback function suitable for before_agent_callback.
    """

    def callback(callback_context: CallbackContext) -> types.Content | None:
        """Write current step status to session state."""
        callback_context.state["current_step"] = step_message
        return None  # Continue with agent execution

    return callback


# Pre-defined callbacks for each pipeline step with human-friendly messages
check_existing_callback = emit_step_status("Checking for existing pages...")
research_callback = emit_step_status("Researching waterfall information...")
content_callback = emit_step_status("Writing engaging content...")
create_in_cms_callback = emit_step_status("Creating page in CMS...")
