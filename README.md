# Skills

Agent skills organized by platform dependency.

## Structure

```
skills-repo/
  pure/        # Pure markdown logic — no runtime dependencies
  openclaw/    # OpenClaw-specific (uses - subagents, WebChat canvas, ACP, cron)
  claude/      # Claude Code-specific (uses - context: fork, hooks, Claude-only features)
```

## Installing

### Claude Code (and other agents)

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

**Option 1 — Clone and symlink into a workspace**

Clone the repo once, then symlink individual skills into whichever workspace needs them:

```bash
git clone https://github.com/EliKhitrov/agent-skills.git ~/agent-skills

# symlink into a specific workspace (repeat per workspace as needed)
ln -s ~/agent-skills/pure/cli-cmd <workspace>/skills/<skill-name>
```

Only symlink what the workspace actually uses — skills load into the agent's context, so keep it selective.

**Option 2 — Install from ClawHub**

```bash
openclaw skills install @EliKhitrov/<skill-name>
```
