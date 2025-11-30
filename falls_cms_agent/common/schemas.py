"""Pydantic schemas shared between ADK agent and MCP server.

These schemas define the data contract between:
1. The ADK agent (which generates structured output)
2. The MCP server (which validates tool inputs)
3. The Rails API (which stores the data)

Keep these in sync across all services!
"""

from enum import Enum

from pydantic import BaseModel, Field, field_validator

# =============================================================================
# Utility Functions
# =============================================================================


def normalize_category_name(name: str) -> str:
    """Normalize category name to title case for proper nouns.

    Handles common geographic naming conventions:
    - "southern oregon" -> "Southern Oregon"
    - "columbia river gorge" -> "Columbia River Gorge"
    - "highway 138" -> "Highway 138"
    - "costa rica" -> "Costa Rica"
    """
    if not name:
        return name

    # Title case the name
    normalized = name.strip().title()

    # Handle common lowercase words that should stay lowercase in titles
    # (unless they're the first word)
    lowercase_words = {"of", "the", "and", "in", "at", "to", "for", "on"}
    words = normalized.split()
    if not words:
        return normalized

    result = [words[0]]  # Keep first word as-is (title case)
    for word in words[1:]:
        if word.lower() in lowercase_words:
            result.append(word.lower())
        else:
            result.append(word)

    return " ".join(result)


# =============================================================================
# Enums - Strict values that match Rails validations
# =============================================================================


class IntentAction(str, Enum):
    """Actions the router can classify user requests into."""

    CREATE_PAGE = "CREATE_PAGE"
    CREATE_CATEGORY = "CREATE_CATEGORY"
    MOVE_PAGE = "MOVE_PAGE"
    RENAME_PAGE = "RENAME_PAGE"
    UPDATE_CONTENT = "UPDATE_CONTENT"
    UPDATE_METADATA = "UPDATE_METADATA"
    PUBLISH_PAGE = "PUBLISH_PAGE"
    UNPUBLISH_PAGE = "UNPUBLISH_PAGE"
    ADD_TO_NAV = "ADD_TO_NAV"
    REMOVE_FROM_NAV = "REMOVE_FROM_NAV"
    SEARCH_CMS = "SEARCH_CMS"
    LIST_PAGES = "LIST_PAGES"
    GET_PAGE = "GET_PAGE"
    HELP = "HELP"


class Difficulty(str, Enum):
    """Trail difficulty levels - must match Rails enum."""

    EASY = "Easy"
    MODERATE = "Moderate"
    HARD = "Hard"


class HikeType(str, Enum):
    """Hike type categories - must match Rails enum."""

    LOOP = "Loop"
    OUT_AND_BACK = "Out and Back"
    POINT_TO_POINT = "Point to Point"


# =============================================================================
# Intent Classification (Router Output)
# =============================================================================


class UserIntent(BaseModel):
    """Structured output from the router agent classifying user intent."""

    reasoning: str = Field(
        description="Brief explanation of why this action was chosen (1-2 sentences)"
    )
    action: IntentAction = Field(description="The classified action type")
    target_page_name: str | None = Field(
        default=None, description="Name of the page being acted upon (for most actions)"
    )
    destination_parent_name: str | None = Field(
        default=None, description="Target parent/category for MOVE_PAGE or CREATE_PAGE"
    )
    search_query: str | None = Field(
        default=None, description="Search terms for SEARCH_CMS or LIST_PAGES"
    )
    content_description: str | None = Field(
        default=None, description="What content to update for UPDATE_CONTENT"
    )
    nav_location_name: str | None = Field(
        default=None, description="Nav location name for ADD_TO_NAV or REMOVE_FROM_NAV (e.g., 'Primary Nav')"
    )


# =============================================================================
# Content Blocks
# =============================================================================


class ContentBlock(BaseModel):
    """A single content block for a page.

    Block names must match the template's cjBlock* IDs.
    Template 4 (Waterfall - Smart Sidebar) uses:
    - cjBlockHero
    - cjBlockIntroduction
    - cjBlockHikingTips
    - cjBlockSeasonalInfo
    - cjBlockPhotographyTips
    - cjBlockDirections
    - cjBlockAdditionalInfo
    - cjBlockGallery
    """

    name: str = Field(description="Block identifier (e.g., 'cjBlockHero')")
    content: str = Field(description="HTML content for the block")


# =============================================================================
# Page Creation Drafts
# =============================================================================


class WaterfallPageDraft(BaseModel):
    """Complete draft for creating a waterfall/location page.

    This is the output schema for the content agent and the input
    for the MCP create_waterfall_page tool.
    """

    title: str = Field(description="Page title (e.g., 'Multnomah Falls')")
    slug: str | None = Field(
        default=None, description="URL slug (auto-generated from title if not provided)"
    )
    meta_title: str = Field(description="SEO title (50-60 characters)")
    meta_description: str = Field(description="SEO description (150-160 characters)")
    difficulty: Difficulty = Field(description="Trail difficulty rating")
    distance: float | None = Field(default=None, description="Trail distance in miles")
    elevation_gain: int | None = Field(default=None, description="Elevation gain in feet")
    hike_type: HikeType = Field(description="Type of hike")
    gps_latitude: float | None = Field(
        default=None, ge=-90, le=90, description="GPS latitude coordinate"
    )
    gps_longitude: float | None = Field(
        default=None, ge=-180, le=180, description="GPS longitude coordinate"
    )
    blocks: list[ContentBlock] = Field(description="Content blocks for the page")

    def to_api_dict(self, parent_id: int | None = None) -> dict:
        """Convert to Rails API format."""
        data = {
            "title": self.title,
            "meta_title": self.meta_title,
            "meta_description": self.meta_description,
            "difficulty": self.difficulty.value,
            "hike_type": self.hike_type.value,
            "layout_template_id": 1,  # Default layout
            "page_template_id": 4,  # Waterfall template
            "blocks_attributes": [{"name": b.name, "content": b.content} for b in self.blocks],
        }
        if self.slug:
            data["slug"] = self.slug
        if self.distance is not None:
            data["distance"] = self.distance
        if self.elevation_gain is not None:
            data["elevation_gain"] = self.elevation_gain
        if self.gps_latitude is not None:
            data["gps_latitude"] = self.gps_latitude
        if self.gps_longitude is not None:
            data["gps_longitude"] = self.gps_longitude
        if parent_id is not None:
            data["parent_id"] = parent_id
        return data

    def to_mcp_dict(self, parent_id: int | None = None) -> dict:
        """Convert to MCP tool format for create_waterfall_page."""
        data = {
            "title": self.title,
            "meta_title": self.meta_title,
            "meta_description": self.meta_description,
            "difficulty": self.difficulty.value,
            "hike_type": self.hike_type.value,
            "blocks": [{"name": b.name, "content": b.content} for b in self.blocks],
        }
        if self.slug:
            data["slug"] = self.slug
        if self.distance is not None:
            data["distance"] = self.distance
        if self.elevation_gain is not None:
            data["elevation_gain"] = self.elevation_gain
        if self.gps_latitude is not None:
            data["gps_latitude"] = self.gps_latitude
        if self.gps_longitude is not None:
            data["gps_longitude"] = self.gps_longitude
        if parent_id is not None:
            data["parent_id"] = parent_id
        return data


class Category(BaseModel):
    """A category for organizing waterfall pages.

    Title is automatically normalized (costa rica -> Costa Rica).
    Can represent both existing (has id) and new categories.

    This is a deterministic model - the LLM extracts the raw name,
    and the validator ensures proper formatting regardless of input.
    """

    title: str = Field(description="Category title (e.g., 'Oregon', 'Columbia River Gorge')")
    slug: str | None = Field(default=None, description="URL slug")
    parent_id: int | None = Field(default=None, description="Parent page ID for nesting")
    id: int | None = Field(default=None, description="Set if category already exists in CMS")

    @field_validator("title", mode="before")
    @classmethod
    def normalize_title(cls, v: str) -> str:
        """Auto-normalize category names to proper title case."""
        return normalize_category_name(v)

    @property
    def exists(self) -> bool:
        """Whether this category already exists in CMS."""
        return self.id is not None

    def to_mcp_dict(self) -> dict:
        """Convert to MCP create_category_page format."""
        data = {"title": self.title}
        if self.slug:
            data["slug"] = self.slug
        if self.parent_id is not None:
            data["parent_id"] = self.parent_id
        return data

    def to_api_dict(self) -> dict:
        """Convert to Rails API format."""
        data = {
            "title": self.title,
            "layout_template_id": 1,
            "page_template_id": 1,  # Simple page template
        }
        if self.slug:
            data["slug"] = self.slug
        if self.parent_id is not None:
            data["parent_id"] = self.parent_id
        return data

    @classmethod
    def from_api_response(cls, data: dict) -> "Category":
        """Create from CMS API response (existing category)."""
        return cls(
            id=data["id"],
            title=data["title"],  # Will be normalized by validator
            slug=data.get("slug"),
            parent_id=data.get("parent_id"),
        )


# Alias for backwards compatibility
CategoryPageDraft = Category


class PageMetadataUpdate(BaseModel):
    """Partial update for page metadata (not content blocks)."""

    title: str | None = Field(default=None)
    slug: str | None = Field(default=None)
    meta_title: str | None = Field(default=None)
    meta_description: str | None = Field(default=None)
    difficulty: Difficulty | None = Field(default=None)
    distance: float | None = Field(default=None)
    elevation_gain: int | None = Field(default=None)
    hike_type: HikeType | None = Field(default=None)
    gps_latitude: float | None = Field(default=None, ge=-90, le=90)
    gps_longitude: float | None = Field(default=None, ge=-180, le=180)

    def to_api_dict(self) -> dict:
        """Convert to Rails API format, excluding None values."""
        data = {}
        if self.title is not None:
            data["title"] = self.title
        if self.slug is not None:
            data["slug"] = self.slug
        if self.meta_title is not None:
            data["meta_title"] = self.meta_title
        if self.meta_description is not None:
            data["meta_description"] = self.meta_description
        if self.difficulty is not None:
            data["difficulty"] = self.difficulty.value
        if self.distance is not None:
            data["distance"] = self.distance
        if self.elevation_gain is not None:
            data["elevation_gain"] = self.elevation_gain
        if self.hike_type is not None:
            data["hike_type"] = self.hike_type.value
        if self.gps_latitude is not None:
            data["gps_latitude"] = self.gps_latitude
        if self.gps_longitude is not None:
            data["gps_longitude"] = self.gps_longitude
        return data


# =============================================================================
# Research Results
# =============================================================================


class ResearchResult(BaseModel):
    """Structured output from the research agent."""

    waterfall_name: str = Field(description="Verified name of the waterfall")
    verified: bool = Field(
        description="Whether the waterfall was verified to exist via credible sources"
    )
    location_state: str | None = Field(default=None, description="State (e.g., 'Oregon')")
    location_region: str | None = Field(
        default=None, description="Region (e.g., 'Columbia River Gorge')"
    )
    gps_latitude: float | None = Field(default=None, ge=-90, le=90)
    gps_longitude: float | None = Field(default=None, ge=-180, le=180)
    distance_miles: float | None = Field(default=None, description="Trail distance in miles")
    elevation_gain_feet: int | None = Field(default=None, description="Elevation gain in feet")
    difficulty: Difficulty | None = Field(default=None)
    hike_type: HikeType | None = Field(default=None)
    waterfall_height_feet: int | None = Field(default=None)
    description: str = Field(description="2-3 paragraphs of factual information")
    notable_features: list[str] = Field(default_factory=list)
    best_time_to_visit: str | None = Field(default=None)
    parking_info: str | None = Field(default=None)
    fees: str | None = Field(default=None)
    accessibility_notes: str | None = Field(default=None)
    sources: list[str] = Field(description="URLs of sources consulted")
    verification_notes: str | None = Field(
        default=None, description="Notes on why verification failed, if applicable"
    )


# =============================================================================
# API Response Models (for type hints)
# =============================================================================


class PageSummary(BaseModel):
    """Summary of a page from list_pages."""

    id: int
    title: str
    slug: str
    published: bool
    parent_id: int | None = None
    difficulty: str | None = None
    distance: float | None = None
    block_count: int = 0

    @classmethod
    def from_api_dict(cls, data: dict) -> "PageSummary":
        """Create from MCP/API response dict."""
        return cls(
            id=data["id"],
            title=data["title"],
            slug=data.get("slug", ""),
            published=data.get("published", False),
            parent_id=data.get("parent_id"),
            difficulty=data.get("difficulty"),
            distance=data.get("distance"),
            block_count=data.get("block_count", 0),
        )


class PageListResult(BaseModel):
    """Structured result from list/search pages operations.

    Returns a list of pages with context about what filter was applied.
    Use this for composable operations - the pages list can be used by
    other tools or the LLM for follow-up actions.
    """

    pages: list[PageSummary] = Field(description="List of matching pages")
    total_count: int = Field(description="Number of pages returned")
    filter_applied: str = Field(
        description="Description of filter (e.g., 'top-level only', 'all pages')"
    )
    formatted_list: str = Field(
        default="",
        description="Pre-formatted bullet list of pages. Present this to the user as-is.",
    )

    @classmethod
    def create(
        cls,
        pages: list[PageSummary],
        filter_applied: str,
    ) -> "PageListResult":
        """Create a PageListResult with auto-generated formatted_list."""
        if not pages:
            formatted = "No pages found."
        else:
            lines = [f"Found {len(pages)} page(s) ({filter_applied}):\n"]
            for p in pages:
                status = "published" if p.published else "draft"
                lines.append(f"- {p.title} (ID: {p.id}, {status})")
            formatted = "\n".join(lines)

        return cls(
            pages=pages,
            total_count=len(pages),
            filter_applied=filter_applied,
            formatted_list=formatted,
        )


class PageDetail(BaseModel):
    """Full page details from get_page."""

    id: int
    title: str
    slug: str
    published: bool
    parent_id: int | None = None
    meta_title: str | None = None
    meta_description: str | None = None
    difficulty: str | None = None
    distance: float | None = None
    elevation_gain: int | None = None
    hike_type: str | None = None
    gps_latitude: float | None = None
    gps_longitude: float | None = None
    blocks: list[ContentBlock] = Field(default_factory=list)


# =============================================================================
# Navigation Location Models
# =============================================================================


class NavLocation(BaseModel):
    """A navigation location where pages can be displayed.

    Used for managing page placement in header nav, footer nav, etc.
    """

    id: int
    name: str

    @classmethod
    def from_api_dict(cls, data: dict) -> "NavLocation":
        """Create from MCP/API response dict."""
        return cls(id=data["id"], name=data.get("name", ""))


class NavLocationResult(BaseModel):
    """Result of a nav location operation (add/remove)."""

    message: str
    nav_location: NavLocation
