# Runtime Skill Helpers

This directory is for application runtime helpers related to skills, prompts and analysis policies.

Use it for:

- Skill registry metadata used by the app
- Prompt templates selected by LangChain workflow nodes
- Internal policy labels shared across agents

Current layout:

```text
registry.py
  Maps runtime skill names to prompt templates.

loader.py
  Loads prompt markdown from templates/.

templates/
  System prompts used by LangChain chains.
```

Agent-facing skill instructions live in the repository-level `skills/` directory.
