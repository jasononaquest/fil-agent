"""Prompt definitions for agents.

Prompts are now stored in YAML files in this directory.
Use the prompt loader from core.prompts to load them:

    from falls_cms_agent.core import load_prompt

    instruction = load_prompt("router")
    agent = LlmAgent(instruction=instruction, ...)

Available prompts:
- router.yaml: Intent classification
- research.yaml: Waterfall research
- content.yaml: Content generation with voice
- cms.yaml: CMS operations
- voice.yaml: Brand voice definition (imported by content)
"""

# Re-export the loader for convenience
from ..core.prompts import get_prompt_metadata, load_prompt, load_prompt_with_vars

__all__ = ["load_prompt", "load_prompt_with_vars", "get_prompt_metadata"]
