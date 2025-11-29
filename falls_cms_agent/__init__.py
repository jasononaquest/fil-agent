"""Falls Into Love CMS Agent - ADK-based content management assistant.

This package provides an intelligent CMS assistant that can:
- Create waterfall pages with researched content
- Manage page hierarchy and organization
- Update, publish, and delete pages
- Search and list CMS content

Entry point for ADK is `root_agent` in agent.py.
"""

from . import agent

__all__ = ["agent"]
