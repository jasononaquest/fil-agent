"""Prompt definitions for agents.

Prompts are stored in YAML files in this directory.
Use the prompt loader from core.prompts to load them:

    from falls_cms_agent.core.prompts import load_prompt

    instruction = load_prompt("root")
    agent = LlmAgent(instruction=instruction, ...)

Available prompts:
- root.yaml: Root agent orchestration (main entry point)
- content.yaml: Content generation with GenX voice
- research.yaml: Waterfall research and validation
- router.yaml: Intent classification (reference, not actively used)
"""

# Re-export the loader for convenience
from ..core.prompts import get_prompt_metadata, load_prompt, load_prompt_with_vars

__all__ = ["load_prompt", "load_prompt_with_vars", "get_prompt_metadata"]
