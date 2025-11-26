#!/usr/bin/env python3
"""Test script for the deployed Agent Engine agent."""

import json
from google.cloud import aiplatform
from google.cloud.aiplatform_v1beta1 import ReasoningEngineExecutionServiceClient
from vertexai.preview import reasoning_engines

# Configuration
PROJECT = "fil-mcp"
LOCATION = "us-west1"
AGENT_ID = "304151304521908224"


def test_agent(message: str = "List all pages in the CMS"):
    """Send a message to the deployed agent and print the response."""
    aiplatform.init(project=PROJECT, location=LOCATION)

    # Get the agent
    agent = reasoning_engines.ReasoningEngine(AGENT_ID)
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
        client_options={"api_endpoint": f"{LOCATION}-aiplatform.googleapis.com"}
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
    import sys

    message = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "List all pages in the CMS"
    test_agent(message)
