# CLAUDE.md

This file provides guidance to Claude Code when working with code in this repository.

## Working Approach

**Act as an experienced senior engineer:**
- Make sound engineering decisions independently for implementation details
- Don't ask permission for routine technical choices (function names, file organization, standard patterns)
- DO ask questions for architectural decisions, business logic, or ambiguous requirements
- Anticipate edge cases and handle them proactively
- Write production-quality code with proper error handling
- Apply Python best practices without prompting
- Take ownership - if you see a problem, fix it

## Project Overview

This is a Google ADK (Agent Development Kit) agent that powers conversational content creation for the Falls Into Love CMS. It enables natural language requests like "Create a page for Multnomah Falls in Oregon" and handles research, content crafting, and CMS operations.

**Key Architecture:**
- **Multi-agent system**: Coordinator routes to specialized agents
- **Research Agent**: Uses `google_search` to gather waterfall/trail facts
- **Content Agent**: Transforms research into engaging content with GenX woman voice
- **CMS Agent**: Manages pages via MCP connection to Rails API
- **Pipeline**: SequentialAgent orchestrates the page creation workflow

**Relationship to Other Projects:**
- **Falls Into Love (Rails)**: The main CMS at `/home/fil/falls_into_love/`
- **Falls MCP Server**: The MCP server at `/home/fil/falls_into_love_mcp/`

**For detailed architecture, see**: The agent plan documentation in the main Rails project.

## Development Commands

### Setup
```bash
cd /home/fil/falls_into_love_agent
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env              # Add your API keys
```

### Testing
```bash
pytest tests/test_agents.py -v    # Unit tests (fast, no LLM calls)
pytest tests/ -v                  # All tests
```

### Running the Agent
```bash
# Development UI (recommended)
adk web --port 8001

# Terminal mode
adk run falls_cms_agent

# API server (for integration testing)
adk api_server
```

### Local Full-Stack Testing
```bash
# Terminal 1 - Rails API
cd /home/fil/falls_into_love && bin/dev

# Terminal 2 - MCP Server (SSE mode)
cd /home/fil/falls_into_love_mcp
source .venv/bin/activate
RAILS_API_URL=http://localhost:3000/api/v1 \
RAILS_API_TOKEN=your-token \
MCP_TRANSPORT=sse PORT=8000 python server.py

# Terminal 3 - ADK Agent
cd /home/fil/falls_into_love_agent
source .venv/bin/activate
adk web --port 8001
```

### Code Quality
```bash
ruff check .                      # Lint
ruff check --fix .                # Lint + auto-fix
ruff format .                     # Format code
pytest tests/test_agents.py -v    # Unit tests
```

## Project Structure

```
falls_into_love_agent/
├── falls_cms_agent/              # Main agent package
│   ├── __init__.py
│   ├── agent.py                  # root_agent (coordinator)
│   ├── config.py                 # Environment configuration
│   ├── agents/
│   │   ├── cms.py                # CMS agent (MCP tools)
│   │   ├── content.py            # Content agent (voice/tone)
│   │   └── research.py           # Research agent (google_search)
│   ├── pipelines/
│   │   └── create_page.py        # SequentialAgent for page creation
│   └── prompts/
│       ├── cms.py                # CMS agent instructions
│       ├── content.py            # Content agent instructions (voice)
│       └── research.py           # Research agent instructions
├── tests/
│   ├── fixtures/                 # ADK .test.json files
│   ├── test_agents.py            # Unit tests
│   └── test_evaluations.py       # ADK evaluation tests
├── .env                          # Environment variables (not committed)
├── .env.example                  # Environment template
├── CLAUDE.md                     # Claude Code guidance
└── pyproject.toml                # Project configuration
```

## Agent Architecture

### Pipeline: Create Waterfall Page

```
SequentialAgent: create_waterfall_pipeline
  │
  ├── Step 1: check_existing
  │   └── Check for duplicates, extract parent page info
  │   └── Outputs: DUPLICATE_FOUND or NO_DUPLICATE + PARENT_PAGE
  │
  ├── Step 2: research_agent
  │   └── Web search for waterfall facts (GPS, trail info)
  │   └── Validates waterfall exists (RESEARCH_FAILED if not)
  │
  ├── Step 3: content_agent
  │   └── Transform research into engaging content
  │   └── Apply GenX woman voice/tone
  │   └── Uses hard-coded Template 4 block names
  │
  └── Step 4: create_in_cms
      └── Create page in CMS with parent_id
```

Note: Template block names (cjBlockHero, cjBlockIntroduction, etc.) are hard-coded
in the content agent prompt. Dynamic template discovery was removed as unnecessary
overhead since all waterfall pages use Template 4.

### Pipeline Stop Signals

Agents check for and propagate stop signals:
- `DUPLICATE_FOUND` → Pipeline stops, user asked to confirm
- `RESEARCH_FAILED` → Pipeline stops, user informed waterfall can't be verified
- `PIPELINE_STOP` → Propagated through remaining agents

## Content Voice

The content agent writes as a **GenX woman who loves waterfalls**:
- Personal & Informative - like talking to a friend
- Sarcastic undertone - doesn't take herself too seriously
- Genuine admiration for nature
- Practical - includes info hikers actually need

**Example tone:**
> "Yes, you'll be sharing the trail with approximately 47,000 other people on a summer weekend. But trust me, when you round that corner and see 620 feet of cascading water, you'll forget every single one of them."

## Git Workflow

### Commit Message Format

Use conventional commit style: `type: description`

**Types:**
- `feat:` - New feature (new agent, new capability)
- `fix:` - Bug fix
- `refactor:` - Code refactoring
- `test:` - Adding or updating tests
- `docs:` - Documentation changes
- `chore:` - Maintenance tasks

**Examples:**
- `feat: add pipeline guardrails for duplicates and fake waterfalls`
- `fix: update content blocks to match Template 4`
- `test: add ADK evaluation tests for parent page assignment`

### Pre-Commit Checklist

Before every commit:
1. Run `ruff check .` - no lint errors
2. Run `ruff format --check .` - code is formatted
3. Run `pytest tests/test_agents.py -v` - all tests must pass

Quick one-liner:
```bash
ruff check . && ruff format --check . && pytest tests/test_agents.py -v
```

**NEVER commit if:**
- Ruff reports unfixable lint errors
- Code is not formatted
- Any tests are failing
- Feature is incomplete or non-functional

### When to Commit

Proactively suggest commits when:
- A new agent or pipeline step is added and tested
- Prompt improvements are made and tested
- Bug fixes are verified
- Tests are added or updated

## Environment Variables

Required in `.env`:
```bash
# Google AI (for local development)
GOOGLE_GENAI_USE_VERTEXAI=FALSE
GOOGLE_API_KEY=your-google-ai-key

# MCP Server Connection
MCP_SERVER_URL=http://localhost:8000/sse
MCP_API_KEY=                              # Optional

# For production (Vertex AI)
# GOOGLE_GENAI_USE_VERTEXAI=TRUE
# GOOGLE_CLOUD_PROJECT=your-project
# GOOGLE_CLOUD_LOCATION=us-west1
```

## Testing Strategy

### Unit Tests (`test_agents.py`)
- Agent imports and configuration
- Prompt content verification (voice, block names, guardrails)
- Pipeline structure validation
- **No LLM calls** - fast, safe to run frequently

### ADK Evaluation Tests (`test_evaluations.py`)
- Use ADK's AgentEvaluator framework
- Test files in `.test.json` format
- Verify tool trajectories and response patterns
- **Requires LLM calls** - slower, use for CI/CD

### Test Fixtures (`tests/fixtures/`)
- `duplicate_detection.test.json` - Verify pipeline stops on duplicates
- `fake_waterfall_rejection.test.json` - Verify research validation
- `parent_page_assignment.test.json` - Verify correct parent handling
- `content_blocks.test.json` - Verify Template 4 block names

## Adding New Features

### Adding a New Pipeline Step

1. Create the agent in `agents/` or inline in `pipelines/`
2. Add instructions to `prompts/` if complex
3. Add to the SequentialAgent's `sub_agents` list
4. Update tests in `test_agents.py`
5. Add evaluation fixture if needed

### Modifying Prompts

1. Update the prompt in `prompts/`
2. Run unit tests to verify structure: `pytest tests/test_agents.py -v`
3. Test manually with `adk web --port 8001`
4. Add/update evaluation fixtures if behavior changed

### Adding MCP Tools

MCP tools come from the MCP server, not this project. To add new tools:
1. Add the tool to `/home/fil/falls_into_love_mcp/`
2. Restart the MCP server
3. Update `prompts/cms.py` to document the new tool
4. Update agent instructions to use the new tool

## Deployment to Agent Engine

### Deploy Workflow

**Use the deploy script** - it handles everything automatically:

```bash
cd /home/fil/falls_into_love_agent
./deploy.sh
```

The script:
1. Generates production `.env` in `falls_cms_agent/` (with correct Vertex AI settings)
2. Runs `adk deploy`
3. Extracts and displays the new agent ID
4. Updates this CLAUDE.md with the new ID

After the script completes, deploy Rails:
```bash
cd /home/fil/falls_into_love
kamal deploy
```

**Note**: Rails fetches the agent ID automatically from GCP at deploy time (via `.kamal/secrets`). No manual ID updates needed.

### Environment Configuration

**IMPORTANT**: Local and production use different configurations:

| Setting | Local (`.env` at root) | Production (`falls_cms_agent/.env`) |
|---------|------------------------|-------------------------------------|
| `GOOGLE_GENAI_USE_VERTEXAI` | `FALSE` | `TRUE` |
| `GOOGLE_API_KEY` | Your API key | **NOT SET** (uses ADC) |
| `MCP_SERVER_URL` | `http://localhost:8000/sse` | Cloud Run URL |
| Telemetry | `false` | `true` |

The deploy script generates the production `.env` automatically. Never manually copy the local `.env` to the package directory.

### Current Deployment
- **Resource ID**: `2829544795569913856`
- **Full Resource Name**: `projects/256129779474/locations/us-west1/reasoningEngines/3324940754580668416`
- **Region**: us-west1
- **Project**: fil-mcp

**Note**: ADK `--agent_engine_id` flag is broken (404 on agentEngines endpoint), so each deploy creates a new agent. The deploy script handles updating the ID automatically.

### Testing Deployed Agent
```bash
# CLI test script
python test_deployed_agent.py "List all pages"
python test_deployed_agent.py "Create a page for Snoqualmie Falls"

# View traces in Cloud Console
# https://console.cloud.google.com/traces/list?project=fil-mcp
```

### Delete Old Deployments
```bash
# Via REST API (force=true to delete sessions)
curl -X DELETE \
  "https://us-west1-aiplatform.googleapis.com/v1beta1/projects/256129779474/locations/us-west1/reasoningEngines/3324940754580668416{ID}?force=true" \
  -H "Authorization: Bearer $(gcloud auth print-access-token)"
```

## Nice to Haves (Future Improvements)

This section documents potential improvements identified during architectural review.
These are not needed for current functionality but may become relevant as the project evolves.

### Code Cleanup (Low Priority)

**~~Unused Sub-Agent Definitions~~** ✓ Removed in `ee6d0e3`

**~~Prompt Duplication~~** ✓ Fixed in `1501594`
- Removed `voice.yaml` (duplicated content.yaml)
- Removed `cms.yaml` (unused)
- Moved ROOT_INSTRUCTION to `root.yaml`
- All prompts now use consistent YAML format

### If Adding Multi-Turn Conversations

**ADK Context Caching**
`ContextCacheConfig` can reduce Gemini input token costs by up to 75% for cached content.
Not beneficial for single-turn requests but valuable for multi-turn sessions.
```python
from google.adk.context import ContextCacheConfig
app = App(context_cache_config=ContextCacheConfig(min_tokens=500, ttl_seconds=3600))
```

**ADK Context Compaction**
Sliding window summarization of older events to reduce context size in long sessions.
See: https://google.github.io/adk-docs/context/compaction/

### If ADK Vertex AI Emit Limitations Are Resolved

Currently, sub-agents can't emit events back to the UI when running on Vertex AI Agent Engine.
If this is fixed, consider migrating to:

**SequentialAgent with output_key**
```python
create_pipeline = SequentialAgent(
    name="create_waterfall_pipeline",
    sub_agents=[
        duplicate_checker,   # output_key="duplicate_check"
        research_agent,      # output_key="research_result"
        content_agent,       # output_key="content_draft"
        cms_agent,           # output_key="cms_result"
    ]
)
```
Benefits: Automatic state passing, built-in event tracing, easier testing.

**ADK SessionState instead of ContextVar**
Replace manual `ContextVar` usage with ADK's built-in `context.state`.

### If Adding Multiple Users/Interfaces

**Input Validation**
Add Pydantic validation for user inputs:
```python
class CreatePageRequest(BaseModel):
    waterfall_name: str = Field(..., min_length=2, max_length=100, pattern=r'^[\w\s\-\'\.]+$')
```

**Typed Error Handling**
Replace string-based errors with typed results for programmatic error handling:
```python
class PipelineErrorType(Enum):
    DUPLICATE_FOUND = "duplicate_found"
    RESEARCH_FAILED = "research_failed"
```

### Debugging Improvements (Low Priority)

**MCP Error Path Logging**
Add explicit handling when MCP returns `isError=True`:
```python
if result.isError:
    logger.warning(f"MCP tool {tool_name} failed: {result}")
```
Currently errors are silently swallowed and content parsing is attempted anyway.
