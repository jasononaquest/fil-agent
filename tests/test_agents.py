"""Unit tests for agent configurations and prompts.

These tests verify agent setup without hitting the LLM,
useful for catching configuration errors early.

Run with: pytest tests/test_agents.py -v
"""


class TestAgentImports:
    """Test that all agents can be imported without errors."""

    def test_import_root_agent(self):
        """Root agent should be importable."""
        from falls_cms_agent.agent import root_agent

        assert root_agent is not None
        assert root_agent.name == "falls_cms_assistant"

    def test_import_pipeline_tool(self):
        """Create waterfall pipeline tool should be importable."""
        from falls_cms_agent.pipelines.create_page import create_pipeline_tool

        assert create_pipeline_tool is not None
        assert create_pipeline_tool.func.__name__ == "create_waterfall_page"


class TestAgentConfiguration:
    """Test agent configuration values."""

    def test_root_agent_has_tools(self):
        """Root agent should have 11 pipeline tools including router (no delete)."""
        from falls_cms_agent.agent import root_agent

        assert len(root_agent.tools) == 11
        tool_names = [t.func.__name__ for t in root_agent.tools]
        expected = [
            "classify_intent",  # Router - always called first
            "create_waterfall_page",
            "create_category_page",
            "move_page",
            "rename_page",
            "publish_page",
            "unpublish_page",
            "update_page_content",
            "search_pages",
            "list_pages",
            "get_page_details",
        ]
        assert set(tool_names) == set(expected)


class TestPrompts:
    """Test prompt content and structure using YAML loader."""

    def test_content_prompt_has_voice(self):
        """Content prompt should define the GenX voice."""
        from falls_cms_agent.core.prompts import load_prompt

        instruction = load_prompt("content")

        assert "GenX" in instruction
        assert "sarcastic" in instruction.lower() or "sarcasm" in instruction.lower()

    def test_content_prompt_has_template4_blocks(self):
        """Content prompt should reference Template 4 block names."""
        from falls_cms_agent.core.prompts import load_prompt

        instruction = load_prompt("content")

        assert "cjBlockHero" in instruction
        assert "cjBlockIntroduction" in instruction
        assert "cjBlockHikingTips" in instruction

    def test_research_prompt_has_validation(self):
        """Research prompt should have validation for fake waterfalls."""
        from falls_cms_agent.core.prompts import load_prompt

        instruction = load_prompt("research")

        assert "RESEARCH_FAILED" in instruction or "verified" in instruction.lower()

    def test_router_prompt_has_intent_classification(self):
        """Router prompt should define intent classification."""
        from falls_cms_agent.core.prompts import load_prompt

        instruction = load_prompt("router")

        assert "CREATE_PAGE" in instruction or "intent" in instruction.lower()

    def test_root_prompt_has_tools(self):
        """Root prompt should define available tools."""
        from falls_cms_agent.core.prompts import load_prompt

        instruction = load_prompt("root")

        assert "create_waterfall_page" in instruction
        assert "move_page" in instruction
        assert "search_pages" in instruction


class TestSchemas:
    """Test Pydantic schemas."""

    def test_user_intent_schema(self):
        """UserIntent schema should be valid."""
        from falls_cms_agent.common.schemas import IntentAction, UserIntent

        intent = UserIntent(
            reasoning="User wants to create a page for Multnomah Falls",
            action=IntentAction.CREATE_PAGE,
            target_page_name="Multnomah Falls",
            destination_parent_name="Oregon",
        )

        assert intent.action == IntentAction.CREATE_PAGE
        assert intent.target_page_name == "Multnomah Falls"

    def test_waterfall_page_draft_schema(self):
        """WaterfallPageDraft should convert to API dict."""
        from falls_cms_agent.common.schemas import (
            ContentBlock,
            Difficulty,
            HikeType,
            WaterfallPageDraft,
        )

        draft = WaterfallPageDraft(
            title="Test Falls",
            meta_title="Test Falls | Falls Into Love",
            meta_description="A beautiful waterfall",
            difficulty=Difficulty.MODERATE,
            hike_type=HikeType.OUT_AND_BACK,
            blocks=[
                ContentBlock(name="cjBlockHero", content="<h1>Test</h1>"),
            ],
        )

        api_dict = draft.to_api_dict(parent_id=42)

        assert api_dict["title"] == "Test Falls"
        assert api_dict["parent_id"] == 42
        assert api_dict["difficulty"] == "Moderate"
        assert len(api_dict["blocks_attributes"]) == 1

    def test_research_result_schema(self):
        """ResearchResult schema should be valid."""
        from falls_cms_agent.common.schemas import ResearchResult

        result = ResearchResult(
            waterfall_name="Multnomah Falls",
            verified=True,
            description="A beautiful multi-tiered waterfall in the Columbia River Gorge",
            sources=["https://example.com/multnomah-falls"],
            location_state="Oregon",
            gps_latitude=45.5762,
            gps_longitude=-122.1158,
        )

        assert result.verified is True
        assert result.gps_latitude == 45.5762
        assert len(result.sources) == 1

    def test_category_normalizes_name(self):
        """Category model should auto-normalize names to title case."""
        from falls_cms_agent.common.schemas import Category

        # Test basic normalization
        cat1 = Category(title="costa rica")
        assert cat1.title == "Costa Rica"

        # Test with lowercase words
        cat2 = Category(title="columbia river gorge")
        assert cat2.title == "Columbia River Gorge"

        # Test already normalized stays the same
        cat3 = Category(title="Oregon")
        assert cat3.title == "Oregon"

        # Test with lowercase words in middle
        cat4 = Category(title="state of washington")
        assert cat4.title == "State of Washington"

    def test_category_from_api_response(self):
        """Category.from_api_response should create a Category with id."""
        from falls_cms_agent.common.schemas import Category

        api_data = {
            "id": 42,
            "title": "costa rica",  # lowercase from API
            "slug": "costa-rica",
            "parent_id": None,
        }

        cat = Category.from_api_response(api_data)
        assert cat.id == 42
        assert cat.title == "Costa Rica"  # Normalized
        assert cat.slug == "costa-rica"
        assert cat.exists is True

    def test_category_to_mcp_dict(self):
        """Category.to_mcp_dict should produce correct format."""
        from falls_cms_agent.common.schemas import Category

        cat = Category(title="southern oregon", parent_id=10)
        mcp_dict = cat.to_mcp_dict()

        assert mcp_dict["title"] == "Southern Oregon"
        assert mcp_dict["parent_id"] == 10


class TestPipelineTools:
    """Test pipeline function tools."""

    def test_create_pipeline_tool_signature(self):
        """Create pipeline tool should have correct signature.

        user_id is read from tool_context.state (injected by ADK).
        """
        import inspect

        from falls_cms_agent.pipelines.create_page import create_waterfall_page

        sig = inspect.signature(create_waterfall_page)
        params = list(sig.parameters.keys())

        assert "waterfall_name" in params
        assert "parent_name" in params
        assert "tool_context" in params  # ADK injects this with state

    def test_management_tools_exist(self):
        """All management pipeline tools should exist (no delete tool)."""
        from falls_cms_agent.pipelines import (
            get_page_pipeline_tool,
            list_pipeline_tool,
            move_pipeline_tool,
            publish_pipeline_tool,
            rename_pipeline_tool,
            search_pipeline_tool,
            unpublish_pipeline_tool,
            update_content_pipeline_tool,
        )

        tools = [
            move_pipeline_tool,
            rename_pipeline_tool,
            publish_pipeline_tool,
            unpublish_pipeline_tool,
            update_content_pipeline_tool,
            search_pipeline_tool,
            list_pipeline_tool,
            get_page_pipeline_tool,
        ]

        assert len(tools) == 8
        for tool in tools:
            assert tool.func is not None


class TestConfig:
    """Test configuration loading."""

    def test_config_has_defaults(self):
        """Config should have default values."""
        from falls_cms_agent.core.config import Config

        assert Config.DEFAULT_MODEL is not None
        assert Config.ROUTER_MODEL is not None

    def test_config_mcp_server_url(self):
        """Config should have MCP server URL method."""
        from falls_cms_agent.core.config import Config

        # Should not raise, even if env var not set
        url = Config.MCP_SERVER_URL
        # Could be None if not configured
        assert url is None or isinstance(url, str)
