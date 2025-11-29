# Falls CMS Agent

> An AI agent that researches, writes, and publishes waterfall hiking guides—turning a 2-hour content creation process into a 60-second conversation.

Built with [Google's Agent Development Kit (ADK)](https://google.github.io/adk-docs/) for the [Kaggle Agents Intensive Capstone](https://www.kaggle.com/competitions/agents-intensive-capstone-project).

![Demo of creating a waterfall page](docs/demo-screenshot.png)

## The Problem

Creating quality content for a hiking/travel blog is tedious:

1. **Research** (30+ min): Search for GPS coordinates, trail distance, elevation gain, difficulty ratings, seasonal info
2. **Write** (60+ min): Transform facts into engaging content with consistent voice/tone
3. **Publish** (15+ min): Navigate CMS, fill forms, set metadata, organize hierarchy

For a site cataloging hundreds of waterfalls, this doesn't scale.

## The Solution

A conversational agent that handles the entire workflow:

```
User: "Create a page for Cherry Creek Falls in Washington"

Agent: ✓ Checking for existing pages...
       ✓ Researching Cherry Creek Falls...
       ✓ Writing engaging content...
       ✓ Creating page in CMS...

       Done! Created 'Cherry Creek Falls' as a draft under 'Washington'
       with 8 content blocks.
```

**One sentence in, published draft out.**

---

## ADK Features Demonstrated

This project demonstrates **6 key concepts** from the ADK course:

| Feature | Implementation |
|---------|----------------|
| **Multi-Agent System** | Root agent orchestrates router + create pipeline + management tools |
| **Tools (MCP)** | Full MCP integration with custom CMS server for CRUD operations |
| **Tools (Google Search)** | Research agent uses `google_search_retrieval` for grounded facts |
| **Sessions & State** | ADK sessions with `user_id` for real-time event streaming to UI |
| **Observability** | OpenTelemetry tracing enabled for debugging and monitoring |
| **Agent Deployment** | Production deployment on Vertex AI Agent Engine + Cloud Run |

### Multi-Model Orchestration

The agent uses different Gemini models for different tasks:

- **Gemini Flash** (`gemini-2.0-flash`): Fast intent classification and routing
- **Gemini Pro** (`gemini-2.5-pro-preview-05-06`): High-quality content generation

This pattern optimizes for both speed (sub-second routing) and quality (nuanced writing).

---

## Architecture

```mermaid
flowchart TB
    subgraph "Client Layer"
        UI[Rails Chat UI<br/>Stimulus + ActionCable]
    end

    subgraph "Agent Engine (Vertex AI)"
        ROOT[Root Agent<br/>Gemini Flash]

        subgraph "Intent Classification"
            ROUTER[classify_intent<br/>Tool]
        end

        subgraph "Create Pipeline"
            DUP[Duplicate<br/>Check]
            RES[Research Agent<br/>Google Search]
            CON[Content Agent<br/>Gemini Pro]
            CMS_CREATE[CMS Create]
        end

        subgraph "Management Tools"
            LIST[list_pages]
            SEARCH[search_pages]
            MOVE[move_page]
            PUB[publish_page]
            UPDATE[update_content]
        end
    end

    subgraph "MCP Server (Cloud Run)"
        MCP[Falls CMS MCP<br/>Python + SSE]
    end

    subgraph "Rails Application"
        API[REST API<br/>/api/v1/*]
        EVENTS[Event Push<br/>/api/internal/*]
        DB[(PostgreSQL)]
    end

    UI <-->|WebSocket| ROOT
    ROOT --> ROUTER
    ROUTER -->|"intent: create"| DUP
    DUP --> RES
    RES --> CON
    CON --> CMS_CREATE
    ROUTER -->|"intent: manage"| LIST & SEARCH & MOVE & PUB & UPDATE

    CMS_CREATE --> MCP
    LIST & SEARCH & MOVE & PUB & UPDATE --> MCP
    MCP <-->|HTTP| API
    ROOT -->|Status Events| EVENTS
    API --> DB
    EVENTS -->|ActionCable| UI

    style ROOT fill:#4285f4,color:#fff
    style RES fill:#34a853,color:#fff
    style CON fill:#ea4335,color:#fff
    style MCP fill:#fbbc04,color:#000
```

### Component Responsibilities

| Component | Role | Key Design Decision |
|-----------|------|---------------------|
| **Root Agent** | Orchestration | Calls `classify_intent` first, then dispatches to appropriate pipeline/tool |
| **Router** | Intent classification | Gemini Flash for sub-second classification into create/manage/query |
| **Research Agent** | Fact gathering | Google Search grounding ensures real data, not hallucinations |
| **Content Agent** | Writing | Gemini Pro for quality; structured output via Pydantic schemas |
| **MCP Server** | CMS bridge | Stateless, deployed on Cloud Run; translates MCP calls to REST |
| **Rails Events** | Real-time UX | HTTP POST to Rails, which broadcasts via ActionCable |

---

## The Create Pipeline

The page creation workflow is a **sequential pipeline** with validation gates:

```mermaid
sequenceDiagram
    participant U as User
    participant R as Root Agent
    participant D as Duplicate Check
    participant S as Research (Search)
    participant C as Content (Pro)
    participant M as MCP/CMS

    U->>R: "Create page for Multnomah Falls"
    R->>D: Check existing pages

    alt Duplicate Found
        D-->>R: DUPLICATE_FOUND
        R-->>U: "Page already exists (ID: 42)"
    else No Duplicate
        D->>S: Research waterfall

        alt Research Failed
            S-->>R: RESEARCH_FAILED
            R-->>U: "Couldn't verify this waterfall exists"
        else Research Success
            S->>C: Generate content
            C->>M: Create page via MCP
            M-->>R: Page created (ID: 123)
            R-->>U: "Created 'Multnomah Falls' as draft"
        end
    end
```

### Pipeline Guardrails

1. **Duplicate Detection**: Prevents creating redundant pages
2. **Research Validation**: Stops if the waterfall can't be verified (no fake content)
3. **Structured Output**: Pydantic schemas ensure valid JSON for CMS API

---

## Real-Time Status Updates

Users see step-by-step progress as the agent works:

```python
# Pipeline emits status events that stream to the UI
await emit_status("Researching Cherry Creek Falls...", "step_start")
# ... agent does work ...
await emit_status("Research complete", "step_complete")
```

Events flow: **Agent → HTTP POST → Rails → ActionCable → Browser**

The UI renders these as animated step bubbles with spinners and checkmarks.

---

## Content Voice

The content agent writes as a **GenX woman who genuinely loves waterfalls**:

- Personal & informative—like advice from a friend who's been there
- Practical—includes the info hikers actually need
- Slight sarcasm—doesn't take herself too seriously

> "Yes, you'll be sharing the trail with approximately 47,000 other people on a summer weekend. But trust me—when you round that corner and see 620 feet of cascading water, you'll forget every single one of them."

This voice is defined in `prompts/content.yaml` and applied consistently across all generated content.

---

## Project Structure

```
falls_cms_agent/
├── agent.py                 # Root agent definition
├── core/
│   ├── callbacks.py         # Status event emission
│   ├── config.py            # Environment configuration
│   ├── mcp_client.py        # MCP connection management
│   └── prompts.py           # YAML prompt loader
├── pipelines/
│   ├── create_page.py       # Page creation orchestration
│   └── management.py        # CRUD tool implementations
├── common/
│   └── schemas.py           # Pydantic models (shared with MCP)
└── prompts/
    ├── root.yaml            # Root agent instructions
    ├── research.yaml        # Research agent instructions
    └── content.yaml         # Content generation + voice
```

---

## Technical Decisions

### Why MCP Instead of Direct API Calls?

MCP (Model Context Protocol) provides:
- **Tool abstraction**: Agent sees `create_waterfall_page`, not HTTP details
- **Stateless bridge**: MCP server can be scaled independently
- **Interoperability**: Same MCP server could serve other agents/clients

### Why Sequential Pipeline Instead of Parallel?

Content creation is inherently sequential:
1. Must check duplicates before researching
2. Must research before writing
3. Must write before publishing

Parallel execution would create race conditions or require complex rollback logic.

### Why Two Gemini Models?

- **Flash for routing**: Intent classification doesn't need deep reasoning
- **Pro for content**: Writing quality matters; Pro produces more nuanced prose

This reduces costs by using the cheaper model for simple classification while reserving Pro for quality-sensitive content generation. (At the time of writing, Gemini 2.0 Flash costs $0.15/1M input tokens vs $1.25/1M for Gemini 2.5 Pro—an 88% reduction for routing calls. [Vertex AI Pricing](https://cloud.google.com/vertex-ai/generative-ai/pricing))

---

## Project Journey

This project evolved through several iterations:

1. **v1**: Single agent with all capabilities → Hard to test, prompts too long
2. **v2**: Multi-agent with handoffs → Complex state management
3. **v3**: Tools-as-Pipelines pattern → Current architecture, testable and maintainable

Key learnings:
- **Structured output** (Pydantic schemas) eliminated parsing errors
- **Event streaming** transformed UX from "waiting..." to visible progress
- **Multi-model** pattern balanced cost and quality effectively

---

## Related Projects

- **[Falls MCP Server](https://github.com/jasononaquest/falls_into_love_mcp)**: MCP bridge to Rails API

---

## License

MIT

---

## Acknowledgments

Built during the [Google & Kaggle AI Agents Intensive](https://www.kaggle.com/learn-guide/5-day-agents) (November 2025).

Thanks to the ADK team for excellent documentation and the course instructors for the architectural patterns that shaped this project.
