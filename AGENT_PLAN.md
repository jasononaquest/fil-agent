# Falls Into Love ADK Agent Plan

## Executive Summary

This document outlines the architecture for a multi-agent system using Google's Agent Development Kit (ADK) to power conversational content creation for the Falls Into Love CMS. The system will enable natural language requests like "Create a page for Multnomah Falls in Oregon" and handle research, content crafting, and CMS operations.

## Research Findings

### ADK Core Concepts

**Agent Types:**
- `LlmAgent`: Core agent with LLM reasoning, tools, and instructions
- `SequentialAgent`: Executes sub-agents in order, sharing state
- `ParallelAgent`: Runs sub-agents concurrently
- `LoopAgent`: Iterative execution until condition met

**Key Constraint - Built-in Tools:**
> "Currently, for each root agent or single agent, only one built-in tool is supported."

This means `google_search` cannot coexist with MCP tools in the same agent. Workaround: wrap specialized agents with `AgentTool` or use `SequentialAgent` pipelines.

**MCP Integration:**
- `MCPToolset` with `SseConnectionParams` for remote MCP servers
- Supports auth headers for bearer token authentication
- Tool filtering available for security
- Must be defined synchronously in `agent.py` for deployment

**State Management:**
- `output_key` property auto-saves agent response to state
- `temp:` prefix for within-invocation data (shared across agent chain)
- `{key}` templating injects state into instructions
- All agents in a `SequentialAgent` share the same `InvocationContext`

**Session/Memory:**
- `InMemorySessionService`: For local development (no persistence)
- `DatabaseSessionService`: SQL persistence (SQLite, PostgreSQL)
- `VertexAiSessionService`: Production-grade managed persistence
- `MemoryService`: Long-term cross-session recall (not needed for MVP)

### Sources

- [ADK Multi-Agent Systems](https://google.github.io/adk-docs/agents/multi-agents/)
- [MCP Tools Integration](https://google.github.io/adk-docs/tools-custom/mcp-tools/)
- [State Management](https://google.github.io/adk-docs/sessions/state/)
- [Built-in Tools](https://google.github.io/adk-docs/tools/built-in-tools/)
- [Cloud Run Deployment](https://google.github.io/adk-docs/deploy/cloud-run/)
- [Google Cloud Blog: ADK and MCP](https://cloud.google.com/blog/topics/developers-practitioners/use-google-adk-and-mcp-with-an-external-server)

---

## Architecture Design

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              User Interface                                  │
│                    (adk web → future Rails /offtrail/assistant)             │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Coordinator Agent                                    │
│  - Receives natural language requests                                        │
│  - Parses intent (create, update, search, etc.)                             │
│  - Routes to appropriate workflow                                            │
│  - Handles disambiguation ("Which Oregon - state or coast region?")         │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                    ┌─────────────────┼─────────────────┐
                    │                 │                 │
                    ▼                 ▼                 ▼
         ┌──────────────────┐ ┌──────────────┐ ┌───────────────────┐
         │  Research Agent  │ │Content Agent │ │    CMS Agent      │
         │  (google_search) │ │  (LLM only)  │ │   (MCP tools)     │
         │                  │ │              │ │                   │
         │ • Web searches   │ │ • Voice/tone │ │ • list_pages      │
         │ • Fact gathering │ │ • Engaging   │ │ • get_page        │
         │ • Data synthesis │ │   writing    │ │ • create_page     │
         └──────────────────┘ └──────────────┘ │ • update_page     │
                                               │ • list_templates  │
                                               └───────────────────┘
```

### Workflow Pipelines

**Pipeline 1: Create Waterfall Page** (Implemented)
```
SequentialAgent: create_waterfall_pipeline
  │
  ├── Step 0: get_template_blocks
  │   └── Fetch Template 4 block names from CMS
  │   └── output_key: "template_info"
  │
  ├── Step 1: check_existing
  │   └── Search for duplicate pages
  │   └── Extract parent page from user request
  │   └── Outputs: DUPLICATE_FOUND or NO_DUPLICATE + PARENT_PAGE line
  │   └── output_key: "duplicate_check"
  │
  ├── Step 2: research_agent
  │   └── Search web for waterfall facts (GPS, trail info, etc.)
  │   └── Validate waterfall exists (outputs RESEARCH_FAILED if not)
  │   └── output_key: "research_results"
  │
  ├── Step 3: content_agent
  │   └── Read research from conversation history
  │   └── Apply GenX woman voice/tone
  │   └── Generate Template 4 blocks as JSON
  │   └── output_key: "crafted_content"
  │
  └── Step 4: create_in_cms
      └── Check for stop signals (DUPLICATE_FOUND, RESEARCH_FAILED)
      └── Create page with parent_id from PARENT_PAGE line
      └── output_key: "created_page"
```

**Pipeline Stop Signals:**
- `DUPLICATE_FOUND` → Pipeline stops, user asked to confirm
- `RESEARCH_FAILED` → Pipeline stops, waterfall couldn't be verified
- `PIPELINE_STOP` → Propagated through remaining agents

**Pipeline 2: Update Existing Page** (Not Yet Implemented)
```
Currently handled by direct CMS agent calls.
The coordinator routes update requests to cms_agent which:
  1. Searches for page by name (never asks user for ID)
  2. Updates the page with requested changes
  3. Supports batch updates (multiple pages at once)
```

**Pipeline 3: Simple Query** (Implemented)
```
Direct CMS Agent call for:
  • "List all pages in Oregon"
  • "Show me the Multnomah Falls page"
  • "What templates are available?"
```

**Note on State Management:**
Originally planned to use `{variable}` injection, but ADK's state management
proved unreliable. Current implementation uses **conversation history** instead -
each agent reads previous agents' output from the conversation context.

### Agent Definitions

#### 1. Research Agent
```python
research_agent = LlmAgent(
    name="research_agent",
    model="gemini-2.0-flash",
    description="Searches the web for waterfall and hiking trail information.",
    instruction="""You are a research specialist for waterfall information.

    When asked to research a waterfall or hiking trail:
    1. Search for official trail information (GPS coordinates, distance, elevation)
    2. Search for difficulty ratings and hike type (loop, out-and-back, etc.)
    3. Search for notable features, best times to visit, and safety information
    4. Synthesize findings into structured data

    Return your findings in this format:
    - Name: [waterfall name]
    - Location: [state/region]
    - GPS: [latitude, longitude]
    - Distance: [miles]
    - Elevation Gain: [feet]
    - Difficulty: [Easy/Moderate/Hard]
    - Hike Type: [Loop/Out and Back/Point to Point]
    - Description: [2-3 paragraphs of factual information]
    - Notable Features: [bullet points]
    - Best Time to Visit: [season/conditions]
    - Sources: [URLs consulted]
    """,
    tools=[google_search],
    output_key="research_results"
)
```

#### 2. Content Agent
```python
content_agent = LlmAgent(
    name="content_agent",
    model="gemini-2.0-flash",
    description="Transforms research into engaging content with brand voice.",
    instruction="""You are the voice of Falls Into Love, a waterfall photography
    and hiking blog written by a GenX woman who genuinely loves waterfalls.

    Your writing style:
    - PERSONAL & INFORMATIVE: Share knowledge like you're talking to a friend
    - SARCASTIC UNDERTONE: Don't take yourself too seriously, gentle self-deprecation is fine
    - GENUINE ADMIRATION: Your love for waterfalls and nature is real and infectious
    - PRACTICAL: Include the info hikers actually need, not fluff

    Example of your voice:
    "Yes, you'll be sharing the trail with approximately 47,000 other people on
    a summer weekend. But trust me, when you round that corner and see 620 feet
    of cascading water, you'll forget every single one of them. Or at least
    you'll be too busy ugly-crying at the beauty to care."

    Transform the research in {research_results} into CMS content blocks:

    1. cjBlockHero: A captivating headline and tagline (HTML)
    2. cjBlockDescription: 2-3 paragraphs of engaging description (HTML)
    3. cjBlockDetails: Trail stats and practical info (HTML)
    4. cjBlockTips: Visitor tips and best practices (HTML)

    Format your output as JSON with this structure:
    {
        "title": "Page title",
        "meta_title": "SEO title",
        "meta_description": "SEO description (150 chars)",
        "difficulty": "Easy|Moderate|Hard",
        "distance": 2.4,
        "elevation_gain": 700,
        "hike_type": "Loop|Out and Back|Point to Point",
        "gps_latitude": 45.5762,
        "gps_longitude": -122.1157,
        "blocks": [
            {"name": "cjBlockHero", "content": "<h1>...</h1><p>...</p>"},
            {"name": "cjBlockDescription", "content": "<p>...</p>"},
            ...
        ]
    }
    """,
    output_key="crafted_content"
)
```

#### 3. CMS Agent
```python
cms_agent = LlmAgent(
    name="cms_agent",
    model="gemini-2.0-flash",
    description="Manages CMS operations via MCP tools.",
    instruction="""You manage the Falls Into Love CMS. You can:

    - List pages (optionally search by title)
    - Get page details including content blocks
    - Create new pages with blocks
    - Update existing pages
    - List available templates

    When creating pages:
    - Pages are created as drafts by default
    - Use page_template_id: 4 for Location pages
    - Set parent_id if the page belongs under a category

    When checking for existing pages:
    - Always search before creating to avoid duplicates
    - Report existing pages to the coordinator for confirmation

    Available MCP tools: list_pages, get_page, create_page, update_page,
    delete_page, list_templates, list_nav_locations
    """,
    tools=[
        MCPToolset(
            connection_params=SseConnectionParams(
                url=os.getenv("MCP_SERVER_URL"),
                headers={"Authorization": f"Bearer {os.getenv('MCP_API_KEY')}"}
            )
        )
    ],
    output_key="cms_result"
)
```

#### 4. Coordinator Agent
```python
coordinator_agent = LlmAgent(
    name="coordinator",
    model="gemini-2.0-flash",
    description="Main entry point that understands user intent and orchestrates workflows.",
    instruction="""You are the coordinator for Falls Into Love content management.

    Your responsibilities:
    1. Understand user requests (create page, update page, search, etc.)
    2. Route to appropriate workflows
    3. Handle disambiguation when needed
    4. Provide status updates throughout the process

    For "create a page for [waterfall]":
    → Use create_waterfall_pipeline

    For "update [page] with [changes]":
    → Use update_page_pipeline

    For simple queries (list, search, show):
    → Use cms_agent directly

    Always confirm before creating or updating content.
    If a page might already exist, check first and ask user to confirm.
    """,
    tools=[
        AgentTool(agent=create_waterfall_pipeline),
        AgentTool(agent=update_page_pipeline),
        AgentTool(agent=cms_agent)
    ]
)
```

---

## Memory Decision

### Recommendation: State Only (No Memory Service for MVP)

**Rationale:**
- Each content creation request is self-contained
- No need to recall past conversations across sessions
- State within a single session is sufficient for multi-step workflows
- Simpler architecture, easier to debug

**Implementation:**
- Use `InMemorySessionService` for local development
- Use `VertexAiSessionService` for production (persists within session)
- Pass data between agents via `output_key` and state injection `{key}`

**Future Enhancement:**
If we later want to remember user preferences (preferred writing style, common categories), we can add `VertexAiMemoryBankService`.

---

## Step Visibility (UI Integration)

### Design for Future UI

The user wants to see agent steps in the eventual Rails chat UI. ADK provides this through **Events**.

**How Events Work:**
- Each agent action produces `Event` objects
- Events contain: author, content, actions, tool calls, tool results
- The `Runner` yields events as they occur

**Streaming to Rails UI:**
```python
async for event in runner.run_async(...):
    # Send event to ActionCable channel
    # UI can display: "Research Agent: Searching for Multnomah Falls..."
    # UI can display: "Content Agent: Crafting hero block..."
    # UI can display: "CMS Agent: Creating page..."
```

**Event Types to Surface:**
- Agent transitions (which agent is active)
- Tool calls (what tool is being invoked)
- Tool results (summary of what was found/done)
- Final outputs (created page URL, etc.)

**Implementation Notes:**
- ADK's `adk web` already renders these steps in its UI
- For Rails integration (Phase 4), we'll stream events via the Agent Engine API
- Consider adding custom events for status messages

---

## Project Structure

```
falls_into_love_agent/
├── .env                    # Environment variables (gitignored)
├── .env.example            # Template for env vars
├── .gitignore
├── pyproject.toml          # Project config + dependencies + ruff config
├── README.md
├── CLAUDE.md               # Claude Code guidance
├── AGENT_PLAN.md           # This document
│
├── Project/
│   └── workflow-guidelines.md  # Development workflow docs
│
├── falls_cms_agent/        # Main agent package
│   ├── __init__.py         # Exports agent module
│   ├── agent.py            # root_agent (coordinator) definition
│   ├── config.py           # Configuration and env loading
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── research.py     # Research agent (google_search)
│   │   ├── content.py      # Content crafting agent
│   │   └── cms.py          # CMS operations agent (MCP)
│   ├── pipelines/
│   │   ├── __init__.py
│   │   └── create_page.py  # 5-step SequentialAgent for page creation
│   └── prompts/
│       ├── __init__.py
│       ├── research.py     # Research agent instructions + validation
│       ├── content.py      # Content agent instructions (voice/tone)
│       └── cms.py          # CMS agent instructions + batch ops
│
└── tests/
    ├── __init__.py
    ├── conftest.py         # Pytest fixtures
    ├── test_agents.py      # Unit tests (16 tests)
    ├── test_evaluations.py # ADK evaluation tests
    └── fixtures/           # ADK .test.json files
        ├── duplicate_detection.test.json
        ├── fake_waterfall_rejection.test.json
        ├── parent_page_assignment.test.json
        └── content_blocks.test.json
```

---

## Environment Configuration

### `.env.example`
```bash
# Google AI / Vertex AI
GOOGLE_GENAI_USE_VERTEXAI=FALSE      # FALSE for local, TRUE for production
GOOGLE_API_KEY=your-api-key          # For local development
GOOGLE_CLOUD_PROJECT=fil-mcp         # For Vertex AI
GOOGLE_CLOUD_LOCATION=us-west1       # For Vertex AI

# MCP Server Connection
MCP_SERVER_URL=http://localhost:8000/sse     # Local MCP server
# MCP_SERVER_URL=https://falls-mcp-server-256129779474.us-west1.run.app/sse  # Production
MCP_API_KEY=                                  # Optional: API key for MCP server auth

# Rails API (for reference - MCP server uses this)
# RAILS_API_URL=https://staging.fallsintolove.com/api/v1
# RAILS_API_TOKEN=your-rails-api-token
```

### Local vs Production

| Setting | Local Development | Production (Vertex AI) |
|---------|------------------|------------------------|
| `GOOGLE_GENAI_USE_VERTEXAI` | FALSE | TRUE |
| Auth | API Key | gcloud ADC |
| MCP URL | localhost:8000 | Cloud Run URL |
| Session Service | InMemorySessionService | VertexAiSessionService |

---

## Implementation Phases

### Phase 3.1: Project Setup ✅
- [x] Create Python project with pyproject.toml
- [x] Set up virtual environment (Python 3.12)
- [x] Install google-adk and dependencies
- [x] Create project structure
- [x] Configure .env for local development

### Phase 3.2: CMS Agent (MCP Integration) ✅
- [x] Implement CMS agent with MCP toolset
- [x] Test connection to local MCP server
- [x] Test connection to Cloud Run MCP server
- [x] Verify all CMS operations work
- [x] Add batch update support (search all pages first, then update)

### Phase 3.3: Research Agent ✅
- [x] Implement Research agent with google_search
- [x] Test web search capabilities
- [x] Tune prompts for waterfall research
- [x] Verify output format for downstream agents
- [x] Add validation guardrail (reject fictional waterfalls)

### Phase 3.4: Content Agent ✅
- [x] Implement Content agent
- [x] Define voice/tone in prompts (GenX woman persona)
- [x] Test content transformation
- [x] Verify JSON output format
- [x] Update to use Template 4 block names (cjBlockHero, cjBlockIntroduction, etc.)

### Phase 3.5: Pipelines & Coordinator ✅
- [x] Implement CreateWaterfallPipeline (5-step SequentialAgent)
- [x] Add template block discovery step (get_template_blocks)
- [x] Add parent page handling (PARENT_PAGE: line in check_existing)
- [x] Add pipeline stop signals (DUPLICATE_FOUND, RESEARCH_FAILED, PIPELINE_STOP)
- [x] Implement Coordinator agent (root_agent in agent.py)
- [x] Test end-to-end workflows
- [ ] Implement UpdatePagePipeline (deferred - direct CMS agent works for now)

### Phase 3.6: Testing & Refinement ✅
- [x] Write unit tests for agents (16 tests in test_agents.py)
- [x] Write ADK evaluation tests (test_evaluations.py with .test.json fixtures)
- [x] Test with `adk web` UI
- [x] Refine prompts based on results
- [x] Add ruff linter and formatter
- [x] Create CLAUDE.md and workflow guidelines
- [x] Document API and usage (README.md)

### Phase 3.7: Deployment Preparation 🚧
- [ ] Test with Vertex AI configuration
- [ ] Document Cloud Run deployment steps
- [ ] Create deployment scripts/Terraform (future)

---

## Future Considerations

### Terraform for IaC
- Cloud Run service configuration
- Vertex AI Agent Engine setup
- IAM permissions
- Secret Manager for API keys

### Logging & Observability
- Cloud Logging for agent events
- Custom metrics for agent performance
- Tracing for multi-agent workflows
- Error alerting

### Security Enhancements
- Add API key auth to MCP server (defense in depth)
- Implement request signing
- Rate limiting on agent API

---

## Commands Reference

```bash
# Setup
cd /home/fil/falls_into_love_agent
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Local Development
adk web --port 8001              # Start dev UI (8001 to avoid MCP conflict)
adk run falls_cms_agent          # Run in terminal mode
adk api_server                   # Start API server for testing

# Code Quality
ruff check .                     # Lint
ruff check --fix .               # Lint + auto-fix
ruff format .                    # Format code

# Testing
pytest tests/test_agents.py -v   # Unit tests (fast, no LLM)
pytest tests/ -v                 # All tests including ADK evaluations

# Pre-commit (all must pass)
ruff check . && ruff format --check . && pytest tests/test_agents.py -v

# Local Full-Stack Testing
# Terminal 1: Rails (localhost:3000)
# Terminal 2: MCP Server (localhost:8000)
# Terminal 3: ADK Agent (localhost:8001)

# Deployment (future)
adk deploy cloud_run \
  --project=$GOOGLE_CLOUD_PROJECT \
  --region=$GOOGLE_CLOUD_LOCATION \
  falls_cms_agent
```

---

## Decisions Made

### Voice & Tone
The content is written from the perspective of a **GenX woman** with:
- **Personal & Informative** style - sharing knowledge like talking to a friend
- A splash of **sarcasm** - not taking herself too seriously
- **Deep admiration for nature** - genuine enthusiasm for waterfalls
- Balance of practical info and personality

Example tone: "Yes, you'll be sharing the trail with approximately 47,000 other people on a summer weekend. But trust me, when you round that corner and see 620 feet of cascading water, you'll forget every single one of them."

### Content Review Strategy
- **Default**: Create pages as drafts without confirmation
- **Exception**: Stop and request human confirmation if duplicate detected
- Rationale: Drafts are safe (not published), but duplicates waste effort

### Error Handling Strategy
- **UI (future)**: Friendly, actionable messages ("I couldn't create the page - the distance value seems invalid")
- **Observability**: Full technical details logged (MCP response codes, stack traces, etc.)
- Implementation: Structured logging to Cloud Logging (future Terraform setup)

### Multi-Page Request Strategy
- **MVP**: Sequential processing with progress updates
- **Rationale**: "Stop for confirmation" on duplicates is much simpler with sequential
- **Future**: Can add parallel optimization once core flow is solid

### Research Sources
- Let agent decide which sources to search
- Agent should cite sources in research output for transparency
- Can tune prompts later if quality issues arise

### Parent Page Handling
- **Auto-create parent as draft** if it doesn't exist
- Inform user what was created: "I created a 'Columbia River Gorge' category page and added Multnomah Falls under it."
- Rationale: Corrections are trivial via conversation ("Actually, rename that to Northern Oregon")
- Keeps workflow moving without interruptions

### State Management (Revised)
- **Original plan**: Use `{variable}` templating to inject state into prompts
- **Actual implementation**: Use **conversation history** instead
- Rationale: ADK's state injection proved unreliable with `KeyError` issues
- Each agent reads previous agents' output from conversation context
- More robust and easier to debug

### Pipeline Guardrails
- **Duplicate detection**: Pipeline stops early if page already exists
- **Research validation**: Requires 2+ credible sources to verify waterfall exists
- **Stop signals**: DUPLICATE_FOUND, RESEARCH_FAILED, PIPELINE_STOP propagate through pipeline
- Rationale: Prevents wasted effort and hallucinated content for fictional waterfalls

### Template Block Discovery
- **Added Step 0**: get_template_blocks fetches available blocks before content creation
- Rationale: Ensures content agent creates blocks that match the actual template
- Fixed bug where content used wrong block names (Template 2 vs Template 4)

### Batch Update Support
- CMS agent always looks up page IDs before updating
- Never asks user for IDs - searches by title
- For multiple pages: searches ALL first, then performs updates
- Rationale: Better UX, agents shouldn't require users to know internal IDs

---

## Success Criteria

### Core Functionality ✅
- [x] Say "Create a page for Toketee Falls in the Waterfalls category" → working draft page created
- [x] Agent performs web research and includes accurate trail data
- [x] Content matches desired voice/tone (GenX woman persona)
- [x] All steps visible in `adk web` UI
- [x] Can update existing pages via natural language
- [x] Can handle batch updates ("Move Watson Falls and Toketee Falls under Highway 138")
- [x] Local development works without Vertex AI account

### Guardrails ✅
- [x] Duplicate detection stops pipeline and asks user
- [x] Fake waterfall detection prevents hallucinated content
- [x] Parent page correctly assigned from user request

### Quality & Testing ✅
- [x] Unit tests pass (16 tests)
- [x] ADK evaluation fixtures created
- [x] Ruff linter configured and passing
- [x] Pre-commit checklist documented

### Pending
- [ ] Deployable to Cloud Run/Vertex AI without code changes
- [ ] Create multiple pages in one request ("Add X, Y, and Z to Oregon")

### Known Limitations
- Cannot filter pages by parent_id (API enhancement documented in MCP project)
- UpdatePagePipeline not implemented (direct CMS agent works for now)
