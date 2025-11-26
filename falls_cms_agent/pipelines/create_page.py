"""Create Waterfall Page Pipeline - orchestrates the full page creation workflow."""

from google.adk.agents import LlmAgent, SequentialAgent

from ..agents.cms import cms_agent
from ..agents.content import content_agent
from ..agents.research import research_agent
from ..config import Config

# Step 1: Check for existing pages (using CMS agent)
check_existing_agent = LlmAgent(
    name="check_existing",
    model=Config.DEFAULT_MODEL,
    description="Checks if a page already exists in the CMS.",
    instruction="""You are step 1 in a page creation pipeline.
Your job is to check if a page for the requested waterfall already exists.

Look at the user's request to identify the waterfall name they want to create.
Use the list_pages tool with that name as a search term.

If a matching page is found:
- Report: "DUPLICATE_FOUND: [page title] (ID: [id])"
- Include the existing page details
- The pipeline should stop here

If no matching page is found:
- Report: "NO_DUPLICATE: [waterfall name]"

CRITICAL - PARENT PAGE HANDLING:
1. Look at the user's ORIGINAL request for any parent/category mention
   (e.g., "in the Waterfalls category", "under Oregon", etc.)
2. If a parent was mentioned, search for it using list_pages
3. Report the parent info in this EXACT format:
   "PARENT_PAGE: [name] (ID: [id])" if found
   "PARENT_PAGE: [name] (NOT_FOUND - will be created)" if not found
   "PARENT_PAGE: none" if user didn't specify one

This PARENT_PAGE line is critical - downstream steps depend on it!
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
    instruction="""You are step 4 (final) in the page creation pipeline.

FIRST: Check the conversation history for stop signals:
- If you see "DUPLICATE_FOUND" → output: "PIPELINE_STOPPED: Duplicate page exists. No page created."
- If you see "PIPELINE_STOP" → output: "PIPELINE_STOPPED: [repeat the reason from earlier]"
- If you see "RESEARCH_FAILED" → output: "PIPELINE_STOPPED: Cannot create page - waterfall could not be verified."

Only proceed with page creation if none of these signals are present.

The content_agent produced JSON content. Look in the conversation history for the JSON object containing:
- title, slug, meta_title, meta_description
- difficulty, distance, elevation_gain, hike_type
- gps_latitude, gps_longitude
- blocks: array of objects with "name" and "content" keys

HANDLING PARENT PAGES - THIS IS CRITICAL:
Look in the conversation history for the check_existing agent's output.
Find the line starting with "PARENT_PAGE:" - it will be one of:
- "PARENT_PAGE: [name] (ID: [id])" → Use that ID as parent_id
- "PARENT_PAGE: [name] (NOT_FOUND - will be created)" → Create a simple page with that title first, then use its ID
- "PARENT_PAGE: none" → Don't set a parent_id

You MUST use the parent_id when creating the page if one was specified!

Use the create_page tool with ALL the extracted data including parent_id.
IMPORTANT: Include ALL blocks from the crafted content - do not skip any blocks!

Report what was created:
"CREATED: [title] (ID: [id]) as draft under [parent name] (parent_id: [id])" or "under root" if no parent
"BLOCKS CREATED: [list all block names that were included]"
""",
    tools=[cms_agent.tools[0]],  # Share the MCP toolset
    output_key="created_page",
)


def create_waterfall_pipeline() -> SequentialAgent:
    """Create the full waterfall page creation pipeline.

    Pipeline steps:
    1. check_existing: Search CMS for duplicates, extract waterfall name & parent
    2. research_agent: Web search for facts (GPS, trail info, etc.)
    3. content_agent: Transform research into engaging content with brand voice
    4. create_in_cms: Create page in CMS with the crafted content

    Data flows via conversation history - each agent reads the previous agent's output.
    State keys set via output_key:
    - duplicate_check (step 1)
    - research_results (step 2)
    - crafted_content (step 3)
    - created_page (step 4)

    Note: Template block names are hard-coded in content agent prompt (Template 4 blocks).
    Dynamic template discovery was removed as unnecessary overhead.
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
