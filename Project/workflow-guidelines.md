# Project Workflow Guidelines

**Purpose**: Maintain top 1% engineering standards with systematic documentation, progress tracking, and consistent commit practices for the Falls Into Love ADK Agent.

## Quality Gates

### Before Every Commit

```bash
# Required - all must pass
pytest tests/test_agents.py -v    # Unit tests

# Verify imports work
python -c "from falls_cms_agent.agent import root_agent; print('✓ Imports OK')"
```

**NEVER commit if:**
- Any tests are failing
- Agent fails to import
- Feature is incomplete or non-functional

### Before Major Releases

```bash
# Full test suite including ADK evaluations
pytest tests/ -v

# Manual verification with adk web
adk web --port 8001
# Test: Create a page, duplicate detection, fake waterfall rejection
```

## Git Commit Strategy

### Commit Frequency Rules

Proactively suggest commits at these trigger points:

1. **Feature Completion** (Required)
   - New agent or pipeline step added and tested
   - New guardrail or validation added

2. **Bug Fixes** (Required)
   - Issue identified and fixed
   - Tests added/updated to prevent regression

3. **Prompt Improvements** (Recommended)
   - Voice/tone adjustments tested
   - Block names or formats corrected

4. **Test Additions** (Recommended)
   - New test fixtures added
   - Coverage improved

### Commit Message Format

**Structure:**
```
{Type}: {Brief description}

{Detailed explanation if needed}

• Bullet points for specific changes
• Test results or metrics

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
```

**Types:**
- `feat:` - New feature (agent, pipeline step, capability)
- `fix:` - Bug fix or correction
- `refactor:` - Code restructuring without behavior change
- `test:` - Test additions or improvements
- `docs:` - Documentation updates
- `chore:` - Maintenance tasks

## Progress Tracking

### Task Management
- Use TodoWrite tool consistently during development
- Break complex work into manageable tasks
- Mark tasks complete immediately upon finishing
- Only one task in_progress at a time

### Documentation
- Keep AGENT_PLAN.md updated with architectural decisions
- Document API/MCP enhancement needs for future work
- Update CLAUDE.md when adding new patterns or commands

## Testing Strategy

### When to Run Which Tests

| Scenario | Command | Purpose |
|----------|---------|---------|
| Before any commit | `pytest tests/test_agents.py -v` | Fast validation |
| After prompt changes | Manual test with `adk web` | Verify behavior |
| Before release | `pytest tests/ -v` | Full validation |
| CI/CD pipeline | `pytest tests/ -v` | Automated checks |

### Test Maintenance

When adding new features:
1. Add unit tests to `test_agents.py` for configuration
2. Add evaluation fixtures to `tests/fixtures/` for behavior
3. Update existing tests if behavior changed

## Development Workflow

### Typical Feature Addition

1. **Plan**: Understand the requirement, check AGENT_PLAN.md
2. **Implement**: Add/modify agents, prompts, or pipeline
3. **Test**: Run unit tests, verify manually with `adk web`
4. **Document**: Update CLAUDE.md or AGENT_PLAN.md if needed
5. **Commit**: Use conventional commit format

### Debugging Agent Issues

1. Check `adk web` UI for step-by-step execution
2. Look for stop signals (DUPLICATE_FOUND, RESEARCH_FAILED)
3. Verify prompts include expected keywords
4. Check MCP server logs for API errors
5. Run unit tests to verify configuration

## Communication Standards

### When Claude Should Prompt for Commits

Proactively ask "Should we commit this work?" when:
- A feature is completed and tested
- A bug is fixed and verified
- Tests are passing after changes
- A logical stopping point is reached

### Progress Reporting

- Provide clear status updates when switching tasks
- Highlight any blockers or architectural decisions
- Summarize progress at natural breakpoints
- Alert to any deviations from expected behavior
