"""Pytest fixtures for agent tests."""

import pytest


@pytest.fixture
def mock_mcp_response():
    """Mock MCP server response for testing."""
    return {
        "pages": [
            {
                "id": 1,
                "title": "Multnomah Falls",
                "slug": "multnomah-falls",
                "published": False,
            }
        ]
    }


@pytest.fixture
def sample_research_results():
    """Sample research results for content agent testing."""
    return {
        "name": "Multnomah Falls",
        "location": "Columbia River Gorge, Oregon",
        "gps_latitude": 45.5762,
        "gps_longitude": -122.1157,
        "distance": 2.4,
        "elevation_gain": 700,
        "difficulty": "Easy",
        "hike_type": "Out and Back",
        "description": "Multnomah Falls is a 620-foot waterfall...",
        "notable_features": ["Benson Bridge", "Two-tiered falls"],
        "best_time_to_visit": "Spring for water flow, fall for fewer crowds",
        "sources": ["https://www.alltrails.com/trail/us/oregon/multnomah-falls"],
    }
