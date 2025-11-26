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

    def test_import_pipeline(self):
        """Create waterfall pipeline should be importable."""
        from falls_cms_agent.pipelines.create_page import create_waterfall_pipeline

        assert create_waterfall_pipeline is not None
        assert create_waterfall_pipeline.name == "create_waterfall_pipeline"


class TestAgentConfiguration:
    """Test agent configuration values."""

    def test_root_agent_has_tools(self):
        """Root agent should have tools configured."""
        from falls_cms_agent.agent import root_agent

        assert len(root_agent.tools) > 0

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


class TestPrompts:
    """Test prompt content and structure."""

    def test_content_prompt_has_voice(self):
        """Content prompt should define the GenX voice."""
        from falls_cms_agent.prompts.content import CONTENT_INSTRUCTION

        assert "GenX" in CONTENT_INSTRUCTION
        assert (
            "sarcastic" in CONTENT_INSTRUCTION.lower() or "sarcasm" in CONTENT_INSTRUCTION.lower()
        )

    def test_content_prompt_has_template4_blocks(self):
        """Content prompt should reference Template 4 block names."""
        from falls_cms_agent.prompts.content import CONTENT_INSTRUCTION

        assert "cjBlockHero" in CONTENT_INSTRUCTION
        assert "cjBlockIntroduction" in CONTENT_INSTRUCTION
        assert "cjBlockHikingTips" in CONTENT_INSTRUCTION
        # Verify old block names are NOT present
        assert "cjBlockDescription" not in CONTENT_INSTRUCTION
        assert "cjBlockDetails" not in CONTENT_INSTRUCTION

    def test_research_prompt_has_validation(self):
        """Research prompt should have validation for fake waterfalls."""
        from falls_cms_agent.prompts.research import RESEARCH_INSTRUCTION

        assert "RESEARCH_FAILED" in RESEARCH_INSTRUCTION
        assert (
            "verify" in RESEARCH_INSTRUCTION.lower() or "validate" in RESEARCH_INSTRUCTION.lower()
        )

    def test_research_prompt_has_duplicate_check(self):
        """Research prompt should check for DUPLICATE_FOUND."""
        from falls_cms_agent.prompts.research import RESEARCH_INSTRUCTION

        assert "DUPLICATE_FOUND" in RESEARCH_INSTRUCTION
        assert "PIPELINE_STOP" in RESEARCH_INSTRUCTION

    def test_cms_prompt_has_batch_operations(self):
        """CMS prompt should handle batch updates."""
        from falls_cms_agent.prompts.cms import CMS_INSTRUCTION

        assert "batch" in CMS_INSTRUCTION.lower() or "multiple pages" in CMS_INSTRUCTION.lower()
        assert "search" in CMS_INSTRUCTION.lower()


class TestPipeline:
    """Test pipeline structure."""

    def test_pipeline_has_five_agents(self):
        """Pipeline should have 5 sub-agents."""
        from falls_cms_agent.pipelines.create_page import create_waterfall_pipeline

        assert len(create_waterfall_pipeline.sub_agents) == 5

    def test_pipeline_agent_order(self):
        """Pipeline agents should be in correct order."""
        from falls_cms_agent.pipelines.create_page import create_waterfall_pipeline

        agent_names = [a.name for a in create_waterfall_pipeline.sub_agents]
        expected = [
            "get_template_blocks",
            "check_existing",
            "research_agent",
            "content_agent",
            "create_in_cms",
        ]
        assert agent_names == expected
