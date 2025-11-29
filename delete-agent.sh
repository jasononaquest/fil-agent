#!/bin/bash
# ===========================================
# Delete a Falls CMS Agent from Vertex AI Agent Engine
# ===========================================
# This script deletes a deployed agent using the REST API.
# Uses configuration from .deploy.env (same as deploy.sh).
#
# Usage:
#   ./delete-agent.sh <agent_id>
#   ./delete-agent.sh <full_resource_name>
#
# Examples:
#   ./delete-agent.sh 9205515968019693568
#   ./delete-agent.sh projects/123456789/locations/us-west1/reasoningEngines/9205515968019693568

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
REGION="${REGION:-us-west1}"

if [[ -z "$PROJECT_NUMBER" ]]; then
    echo "❌ PROJECT_NUMBER not set"
    echo "   Either create .deploy.env or set PROJECT_NUMBER environment variable"
    exit 1
fi

# Parse arguments
if [[ -z "$1" ]]; then
    echo "Usage: $0 <agent_id_or_resource_name>"
    echo ""
    echo "Examples:"
    echo "  $0 9205515968019693568"
    echo "  $0 projects/$PROJECT_NUMBER/locations/$REGION/reasoningEngines/9205515968019693568"
    echo ""
    echo "To list current agents, run:"
    echo "  ./list-agents.sh"
    exit 1
fi

# Extract agent ID from input (handles both formats)
if [[ "$1" == projects/* ]]; then
    # Full resource name provided
    AGENT_ID=$(echo "$1" | grep -oP 'reasoningEngines/\K[0-9]+')
    RESOURCE_NAME="$1"
else
    # Just the ID provided
    AGENT_ID="$1"
    RESOURCE_NAME="projects/$PROJECT_NUMBER/locations/$REGION/reasoningEngines/$AGENT_ID"
fi

if [[ -z "$AGENT_ID" ]]; then
    echo "❌ Could not parse agent ID from: $1"
    exit 1
fi

echo "=== Delete Agent from Agent Engine ==="
echo ""
echo "   Agent ID: $AGENT_ID"
echo "   Resource: $RESOURCE_NAME"
echo ""

# Get access token
echo "🔑 Getting access token..."
ACCESS_TOKEN=$(gcloud auth print-access-token 2>/dev/null) || {
    echo "❌ Failed to get access token. Run: gcloud auth login"
    exit 1
}

# Delete the agent with force=true to handle child sessions
echo "🗑️  Deleting agent (force=true to remove any sessions)..."
RESPONSE=$(curl -s -X DELETE \
    "https://$REGION-aiplatform.googleapis.com/v1/$RESOURCE_NAME?force=true" \
    -H "Authorization: Bearer $ACCESS_TOKEN" \
    -H "Content-Type: application/json")

# Check response
if echo "$RESPONSE" | grep -q '"done": true'; then
    echo ""
    echo "✅ Agent deleted successfully!"
elif echo "$RESPONSE" | grep -q '"error"'; then
    echo ""
    echo "❌ Delete failed:"
    if command -v jq &> /dev/null; then
        echo "$RESPONSE" | jq -r '.error.message // .error'
    else
        echo "$RESPONSE" | grep -oP '"message"\s*:\s*"\K[^"]+' || echo "$RESPONSE"
    fi
    exit 1
else
    echo ""
    echo "⏳ Delete operation started (may take a moment to complete):"
    if command -v jq &> /dev/null; then
        echo "$RESPONSE" | jq .
    else
        echo "$RESPONSE"
    fi
fi

echo ""
