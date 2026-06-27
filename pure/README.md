# pure/

Pure markdown skills. No runtime dependencies — logic lives entirely in the
SKILL.md. Works in any agent that reads the AgentSkills standard.

Each skill is a folder:

```
<skill-name>/
  SKILL.md          # required
  references/       # optional: docs loaded into context when needed
  assets/           # optional: templates, boilerplate
```

No `scripts/` — if a skill needs to run code, it belongs in `openclaw/` or `claude/`.
