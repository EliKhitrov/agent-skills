# Skills

Agent skills organized by platform dependency.

## Structure

```
skills-repo/
  pure/        # Pure markdown logic — no runtime dependencies
  openclaw/    # OpenClaw-specific (subagents, WebChat canvas, ACP, cron)
  claude/      # Claude Code-specific (context: fork, hooks, Claude-only features)
```

### pure/

Skills whose logic lives entirely in the markdown. No subagent dispatch, no
platform APIs, no tool calls that assume a specific runtime. These work in
OpenClaw, Claude Code, Codex, Cursor, Gemini CLI, or any agent that reads
the SKILL.md standard.

When a skill only tells the model *how to think*, it belongs here.

### openclaw/

Skills that depend on OpenClaw runtime capabilities:
- Subagent spawning / ACP task dispatch
- WebChat canvas embeds (`[embed ...]`)
- `~/.openclaw/` paths and state
- Cron / scheduled tasks / standing orders
- `openclaw message send` notifications

### claude/

Skills that depend on Claude Code-specific features:
- `context: fork` subagent isolation
- Claude Code hooks (pre/post tool)
- `.claude/` directory conventions
- `claude --permission-mode bypassPermissions` patterns

## Adding a skill

1. Decide which bucket: does it use runtime APIs? → `openclaw/` or `claude/`. Pure reasoning? → `pure/`.
2. Create `<platform>/<skill-name>/SKILL.md` with name + description frontmatter.
3. Add supporting files under `scripts/`, `references/`, `agents/`, `assets/` as needed.
4. Keep `SKILL.md` lean — move long docs to `references/`, scripts to `scripts/`.

## Installing

**OpenClaw** — add both `openclaw/` and `pure/` to `openclaw.json`:
```json
{
  "skills": {
    "load": {
      "extraDirs": ["~/skills-repo/openclaw", "~/skills-repo/pure"]
    }
  }
}
```

**Claude Code** — symlink `pure/` into `.claude/skills/`:
```bash
ln -s ~/skills-repo/pure ~/.claude/skills/pure
```
