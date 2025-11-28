"""Router agent - classifies user intent for request routing."""

from google.adk.agents import LlmAgent

from ..common.schemas import UserIntent
from ..core.config import Config
from ..core.prompts import load_prompt

# Load router instruction from YAML
ROUTER_INSTRUCTION = load_prompt("router")

# Router agent - fast model for classification
router_agent = LlmAgent(
    name="intent_router",
    model=Config.ROUTER_MODEL,
    description="Classifies user requests into intent categories for routing.",
    instruction=ROUTER_INSTRUCTION,
    output_schema=UserIntent,
)
