"""YAML prompt loader for agent instructions."""

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from .logging import get_logger

logger = get_logger(__name__)

# Prompts directory relative to this file
PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


@lru_cache(maxsize=32)
def load_prompt(name: str) -> str:
    """Load a prompt from a YAML file.

    Prompts are stored in falls_cms_agent/prompts/ as YAML files.
    Each file should have an 'instruction' key with the prompt text.

    Args:
        name: Name of the prompt file (without .yaml extension)

    Returns:
        The instruction string from the YAML file

    Raises:
        FileNotFoundError: If the prompt file doesn't exist
        KeyError: If the file doesn't have an 'instruction' key

    Example:
        >>> instruction = load_prompt("router")
        >>> agent = LlmAgent(instruction=instruction, ...)
    """
    file_path = PROMPTS_DIR / f"{name}.yaml"

    if not file_path.exists():
        raise FileNotFoundError(f"Prompt file not found: {file_path}")

    with open(file_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if "instruction" not in data:
        raise KeyError(f"Prompt file {name}.yaml must have an 'instruction' key")

    logger.debug(f"Loaded prompt: {name}")
    return data["instruction"]


def load_prompt_with_vars(name: str, **variables: Any) -> str:
    """Load a prompt and substitute variables.

    Uses Python string formatting to replace {variable} placeholders.

    Args:
        name: Name of the prompt file
        **variables: Variables to substitute in the prompt

    Returns:
        The instruction string with variables substituted

    Example:
        >>> instruction = load_prompt_with_vars(
        ...     "content",
        ...     waterfall_name="Multnomah Falls",
        ...     research_data=research_json
        ... )
    """
    template = load_prompt(name)
    return template.format(**variables)


def get_prompt_metadata(name: str) -> dict[str, Any]:
    """Get all metadata from a prompt file.

    Returns the entire YAML structure, not just the instruction.
    Useful for prompts that include examples, few-shots, or other metadata.

    Args:
        name: Name of the prompt file

    Returns:
        Dictionary with all keys from the YAML file
    """
    file_path = PROMPTS_DIR / f"{name}.yaml"

    if not file_path.exists():
        raise FileNotFoundError(f"Prompt file not found: {file_path}")

    with open(file_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def list_prompts() -> list[str]:
    """List all available prompt files.

    Returns:
        List of prompt names (without .yaml extension)
    """
    if not PROMPTS_DIR.exists():
        return []

    return [f.stem for f in PROMPTS_DIR.glob("*.yaml")]
