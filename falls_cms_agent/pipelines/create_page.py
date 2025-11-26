"""Create Waterfall Page Pipeline - orchestrates the full page creation workflow."""

from google.adk.agents import LlmAgent, SequentialAgent

from ..config import Config
from ..agents.cms import cms_agent
from ..agents.research import research_agent
from ..agents.content import content_agent


# Step 1: Check for existing pages (using CMS agent)
check_existing_agent = LlmAgent(
    name="check_existing",
    model=Config.DEFAULT_MODEL,
    description="Checks if a page already exists in the CMS.",
    instruction="""Check if a page for the requested waterfall already exists.

Use the list_pages tool with a search term to find matching pages.

If a matching page is found:
- Report: "DUPLICATE_FOUND: [page title] (ID: [id])"
- Include the existing page details

If no matching page is found:
- Report: "NO_DUPLICATE: Proceeding with creation"

Search term to use: {waterfall_name}
""",
    tools=[cms_agent.tools[0]],  # Share the MCP toolset
    output_key="duplicate_check",
)


# Step 2: Research agent (already defined with google_search)
# Uses research_agent from agents/research.py


# Step 3: Content agent (already defined)
# Uses content_agent from agents/content.py


# Step 4: Create the page in CMS
create_in_cms_agent = LlmAgent(
    name="create_in_cms",
    model=Config.DEFAULT_MODEL,
    description="Creates the page in the CMS using the crafted content.",
    instruction="""Create a new page in the CMS using the crafted content.

Read the content from {crafted_content} which should be a JSON object with:
- title, slug, meta_title, meta_description
- difficulty, distance, elevation_gain, hike_type
- gps_latitude, gps_longitude
- blocks: array of {name, content} objects

If a parent page was specified in {parent_page_name}:
1. Search for the parent page
2. If not found, create it as a simple draft page
3. Set parent_id when creating the waterfall page

Use the create_page tool with all the data from the crafted content.

Report what was created:
"CREATED: [title] (ID: [id]) as draft under [parent or 'root']"
""",
    tools=[cms_agent.tools[0]],  # Share the MCP toolset
    output_key="created_page",
)


def create_waterfall_pipeline() -> SequentialAgent:
    """Create the full waterfall page creation pipeline.

    Pipeline steps:
    1. Check for duplicates
    2. Research waterfall information
    3. Craft content with brand voice
    4. Create page in CMS

    Data flows via state:
    - waterfall_name → check_existing
    - research_results → content_agent
    - crafted_content → create_in_cms
    """
    return SequentialAgent(
        name="create_waterfall_pipeline",
        description="Full pipeline to research, write, and create a waterfall page.",
        sub_agents=[
            check_existing_agent,
            research_agent,
            content_agent,
            create_in_cms_agent,
        ],
    )


# Create the pipeline instance
create_waterfall_pipeline = create_waterfall_pipeline()
