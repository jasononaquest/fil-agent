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

    def test_import_cms_agent(self):
        """CMS agent should be importable."""
        from falls_cms_agent.agents.cms import cms_agent

        assert cms_agent is not None
        assert cms_agent.name == "cms_agent"

    def test_import_research_agent(self):
        """Research agent should be importable."""
        from falls_cms_agent.agents.research import research_agent

        assert research_agent is not None
        assert research_agent.name == "research_agent"

    def test_import_content_agent(self):
        """Content agent should be importable."""
        from falls_cms_agent.agents.content import content_agent

        assert content_agent is not None
        assert content_agent.name == "content_agent"

    def test_import_router_agent(self):
        """Router agent should be importable."""
        from falls_cms_agent.agents.router import router_agent

        assert router_agent is not None
        assert router_agent.name == "intent_router"

    def test_import_pipeline_tool(self):
        """Create waterfall pipeline tool should be importable."""
        from falls_cms_agent.pipelines.create_page import create_pipeline_tool

        assert create_pipeline_tool is not None
        assert create_pipeline_tool.func.__name__ == "create_waterfall_page"


class TestAgentConfiguration:
    """Test agent configuration values."""

    def test_root_agent_has_tools(self):
        """Root agent should have 9 pipeline tools configured."""
        from falls_cms_agent.agent import root_agent

        assert len(root_agent.tools) == 9
        tool_names = [t.func.__name__ for t in root_agent.tools]
        expected = [
            "create_waterfall_page",
            "move_page",
            "delete_page",
            "publish_page",
            "unpublish_page",
            "update_page_content",
            "search_pages",
            "list_pages",
            "get_page_details",
        ]
        assert set(tool_names) == set(expected)

    def test_cms_agent_has_mcp_tools(self):
        """CMS agent should have MCP toolset."""
        from falls_cms_agent.agents.cms import cms_agent

        assert len(cms_agent.tools) > 0

    def test_research_agent_has_google_search(self):
        """Research agent should have google_search tool."""
        from falls_cms_agent.agents.research import research_agent

        assert len(research_agent.tools) > 0

    def test_content_agent_has_no_tools(self):
        """Content agent should have no tools (pure LLM)."""
        from falls_cms_agent.agents.content import content_agent

        assert len(content_agent.tools) == 0

    def test_router_agent_has_output_schema(self):
        """Router agent should have UserIntent output schema."""
        from falls_cms_agent.agents.router import router_agent

        assert router_agent.output_schema is not None


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

    def test_voice_prompt_exists(self):
        """Voice prompt YAML should exist."""
        from falls_cms_agent.core.prompts import load_prompt

        instruction = load_prompt("voice")

        assert len(instruction) > 0
        assert "GenX" in instruction or "woman" in instruction.lower()


class TestSchemas:
    """Test Pydantic schemas."""

    def test_user_intent_schema(self):
        """UserIntent schema should be valid."""
        from common.schemas import IntentAction, UserIntent

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
        from common.schemas import ContentBlock, Difficulty, HikeType, WaterfallPageDraft

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
        from common.schemas import ResearchResult

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


class TestPipelineTools:
    """Test pipeline function tools."""

    def test_create_pipeline_tool_signature(self):
        """Create pipeline tool should have correct signature."""
        import inspect

        from falls_cms_agent.pipelines.create_page import create_waterfall_page

        sig = inspect.signature(create_waterfall_page)
        params = list(sig.parameters.keys())

        assert "waterfall_name" in params
        assert "parent_name" in params
        assert "session_id" in params

    def test_management_tools_exist(self):
        """All management pipeline tools should exist."""
        from falls_cms_agent.pipelines import (
            delete_pipeline_tool,
            get_page_pipeline_tool,
            list_pipeline_tool,
            move_pipeline_tool,
            publish_pipeline_tool,
            search_pipeline_tool,
            unpublish_pipeline_tool,
            update_content_pipeline_tool,
        )

        tools = [
            move_pipeline_tool,
            delete_pipeline_tool,
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
