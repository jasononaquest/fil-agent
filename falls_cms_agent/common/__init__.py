"""Common schemas shared between agent and MCP server."""

from .schemas import (
    CategoryPageDraft,
    # Content structures
    ContentBlock,
    IntentAction,
    PageDetail,
    PageMetadataUpdate,
    # API responses
    PageSummary,
    # Research
    ResearchResult,
    # Intent classification
    UserIntent,
    WaterfallPageDraft,
)

__all__ = [
    "UserIntent",
    "IntentAction",
    "ContentBlock",
    "WaterfallPageDraft",
    "CategoryPageDraft",
    "PageMetadataUpdate",
    "ResearchResult",
    "PageSummary",
    "PageDetail",
]
