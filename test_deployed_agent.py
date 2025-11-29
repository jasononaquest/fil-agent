#!/usr/bin/env python3
"""Test script for the deployed Agent Engine agent.

Configuration:
  Set these environment variables or use .deploy.env:
    - PROJECT_ID (or GOOGLE_CLOUD_PROJECT)
    - REGION (default: us-west1)
    - AGENT_ID (required)

Usage:
  python test_deployed_agent.py "List all pages"
  python test_deployed_agent.py "Create a page for Snoqualmie Falls"
"""

import json
import os
import sys
from pathlib import Path

from google.cloud import aiplatform
from google.cloud.aiplatform_v1beta1 import ReasoningEngineExecutionServiceClient
from vertexai.preview import reasoning_engines


def load_deploy_env():
    """Load configuration from .deploy.env if it exists."""
    deploy_env = Path(__file__).parent / ".deploy.env"
    if deploy_env.exists():
        with open(deploy_env) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    # Don't override existing env vars
                    if key not in os.environ:
                        os.environ[key] = value


def get_config():
    """Get configuration from environment variables."""
    load_deploy_env()

    project = os.getenv("PROJECT_ID") or os.getenv("GOOGLE_CLOUD_PROJECT")
    region = os.getenv("REGION", "us-west1")
    agent_id = os.getenv("AGENT_ID")

    if not project:
        print("❌ PROJECT_ID or GOOGLE_CLOUD_PROJECT not set")
        print("   Set environment variable or create .deploy.env")
        sys.exit(1)

    if not agent_id:
        print("❌ AGENT_ID not set")
        print("   Set environment variable or add to .deploy.env")
        print("   Run ./list-agents.sh to see available agents")
        sys.exit(1)

    return project, region, agent_id


def test_agent(message: str = "List all pages in the CMS"):
    """Send a message to the deployed agent and print the response."""
    project, location, agent_id = get_config()

    aiplatform.init(project=project, location=location)

    # Get the agent
    agent = reasoning_engines.ReasoningEngine(agent_id)
    print(f"Agent: {agent.display_name}")
    print(f"Resource: {agent.resource_name}")

    # Create a session
    session = agent.create_session(user_id="test-user")
    print(f"Session: {session['id']}")
    print("-" * 60)
    print(f"Query: {message}")
    print("-" * 60)

    # Stream the response
    client = ReasoningEngineExecutionServiceClient(
        client_options={"api_endpoint": f"{location}-aiplatform.googleapis.com"}
    )

    request = {
        "name": agent.resource_name,
        "input": {
            "message": message,
            "user_id": "test-user",
            "session_id": session["id"],
        },
        "class_method": "stream_query",
    }

    responses = client.stream_query_reasoning_engine(request=request)
    final_text = ""

    for response in responses:
        if response.data:
            data = json.loads(response.data)
            content = data.get("content", {})
            parts = content.get("parts", [])

            for part in parts:
                # Print tool calls
                if "function_call" in part:
                    fc = part["function_call"]
                    print(f"\n[Tool Call] {fc['name']}: {fc.get('args', {})}")

                # Print tool responses
                if "function_response" in part:
                    fr = part["function_response"]
                    result = fr.get("response", {}).get("result", "")
                    print(f"[Tool Response] {result[:200]}...")

                # Collect final text
                if "text" in part:
                    final_text = part["text"]

    print("-" * 60)
    print("Final Response:")
    print(final_text)
    print("-" * 60)


if __name__ == "__main__":
    message = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "List all pages in the CMS"
    test_agent(message)
