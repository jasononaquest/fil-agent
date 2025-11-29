#!/bin/bash
# ===========================================
# List Falls CMS Agents in Vertex AI Agent Engine
# ===========================================
# Shows all deployed reasoning engines in the project.
# Uses configuration from .deploy.env (same as deploy.sh).
#
# Usage: ./list-agents.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_ENV="$SCRIPT_DIR/.deploy.env"

# Load configuration
if [[ -f "$DEPLOY_ENV" ]]; then
    # shellcheck source=/dev/null
    source "$DEPLOY_ENV"
fi

# Allow environment variable overrides, with defaults for required values
PROJECT_NUMBER="${PROJECT_NUMBER:-}"
PROJECT_ID="${PROJECT_ID:-}"
REGION="${REGION:-us-west1}"

if [[ -z "$PROJECT_NUMBER" ]]; then
    echo "❌ PROJECT_NUMBER not set"
    echo "   Either create .deploy.env or set PROJECT_NUMBER environment variable"
    exit 1
fi

echo "=== Deployed Agents in Agent Engine ==="
echo ""
echo "   Project: ${PROJECT_ID:-$PROJECT_NUMBER}"
echo "   Region: $REGION"
echo ""

# Get access token
ACCESS_TOKEN=$(gcloud auth print-access-token 2>/dev/null) || {
    echo "❌ Failed to get access token. Run: gcloud auth login"
    exit 1
}

# List reasoning engines
RESPONSE=$(curl -s \
    "https://$REGION-aiplatform.googleapis.com/v1/projects/$PROJECT_NUMBER/locations/$REGION/reasoningEngines" \
    -H "Authorization: Bearer $ACCESS_TOKEN" \
    -H "Content-Type: application/json")

# Check for errors
if echo "$RESPONSE" | grep -q '"error"'; then
    echo "❌ Failed to list agents:"
    echo "$RESPONSE" | jq -r '.error.message // .error' 2>/dev/null || echo "$RESPONSE"
    exit 1
fi

# Parse and display agents
if command -v jq &> /dev/null; then
    AGENTS=$(echo "$RESPONSE" | jq -r '.reasoningEngines // []')

    if [[ "$AGENTS" == "[]" ]] || [[ -z "$AGENTS" ]]; then
        echo "No agents deployed."
    else
        echo "$RESPONSE" | jq -r '.reasoningEngines[] | "Agent ID: \(.name | split("/") | last)\n  Name: \(.displayName // "unnamed")\n  Created: \(.createTime)\n  Resource: \(.name)\n"'
    fi
else
    # Fallback without jq - use grep/sed
    if echo "$RESPONSE" | grep -q '"reasoningEngines"'; then
        echo "Agents (install jq for prettier output):"
        echo ""
        # Only match full resource names containing reasoningEngines
        echo "$RESPONSE" | grep -oP 'projects/[^"]+/reasoningEngines/[0-9]+' | while read -r name; do
            AGENT_ID=$(echo "$name" | grep -oP 'reasoningEngines/\K[0-9]+' || true)
            echo "  Agent ID: $AGENT_ID"
            echo "  Resource: $name"
            echo ""
        done || true
    else
        echo "No agents deployed."
    fi
fi

echo ""
