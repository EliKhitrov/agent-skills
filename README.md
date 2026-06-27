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

## Installing

### Claude Code (and other agents)

Requires [Node.js](https://nodejs.org) (for `npx`). Works on Windows, macOS, and Linux.

Install pure skills (work in any agent):
```bash
npx skills@latest add EliKhitrov/agent-skills/pure
```

Install Claude Code-specific skills:
```bash
npx skills@latest add EliKhitrov/agent-skills/claude
```

The `skills` CLI will present a picker, let you choose which skills to install, and place them in the right directory for your agent automatically.

### OpenClaw

Add both `openclaw/` and `pure/` to `openclaw.json`:
```json
{
  "skills": {
    "load": {
      "extraDirs": ["~/agent-skills/openclaw", "~/agent-skills/pure"]
    }
  }
}
```
