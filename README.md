# Falls Into Love ADK Agent

A conversational AI agent for managing content in the Falls Into Love CMS. Built with Google's Agent Development Kit (ADK).

## Features

- **Natural Language Content Creation**: "Create a page for Multnomah Falls in Oregon"
- **Web Research**: Automatically searches for waterfall facts (GPS, trail info, etc.)
- **Brand Voice**: Content crafted with personality (GenX woman who loves waterfalls)
- **CMS Integration**: Creates/updates pages via MCP connection to Rails API

## Architecture

```
Coordinator Agent
    ├── Research Agent (google_search)
    ├── Content Agent (voice/tone)
    └── CMS Agent (MCP tools)
```

See [AGENT_PLAN.md](AGENT_PLAN.md) for detailed architecture documentation.

## Setup

### Prerequisites

- Python 3.12+
- Google AI API key (or Vertex AI access)
- MCP server running (local or Cloud Run)

### Installation

```bash
# Clone and enter directory
cd falls_into_love_agent

# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -e ".[dev]"

# Copy and configure environment
cp .env.example .env
# Edit .env with your API keys
```

### Running Locally

```bash
# Start the dev UI
adk web

# Or run in terminal mode
adk run falls_cms_agent
```

Open http://localhost:8000 and select `falls_cms_agent` from the dropdown.

## Development

```bash
# Run tests
pytest

# Run specific test
pytest tests/test_agents.py -v
```

## MCP Server

This agent connects to the Falls Into Love MCP server for CMS operations.

**Local development**: Run the MCP server first:
```bash
cd ../falls_into_love_mcp
source .venv/bin/activate
python server.py
```

**Production**: Uses Cloud Run deployment at `https://falls-mcp-server-*.run.app/sse`

## Deployment

See [AGENT_PLAN.md](AGENT_PLAN.md) for Cloud Run and Vertex AI deployment instructions.


Local Testing (Full Stack)

Terminal 1 - Rails API:
cd /home/fil/falls_into_love
bin/dev
# Runs on localhost:3000

Terminal 2 - MCP Server (SSE mode):
cd /home/fil/falls_into_love_mcp
source .venv/bin/activate

# Point to local Rails and run in SSE mode
RAILS_API_URL=http://localhost:3000/api/v1 \
RAILS_API_TOKEN=your-local-api-token \
MCP_TRANSPORT=sse \
PORT=8000 \
python server.py

Terminal 3 - ADK Agent:
cd /home/fil/falls_into_love_agent
source .venv/bin/activate
adk web

Update ADK's .env for local:
MCP_SERVER_URL=http://localhost:8000/sse