---
name: cli_cmd
description: Answer Linux/shell command questions in a concise, structured format
---

# cli_cmd — Linux Command Style

When answering a Linux/shell command question, always follow this format:

1. A short explanation what the command does
2. Show the command. Choose best option if there are several
3. Follow with a brief syntax breakdown, one bullet per flag/argument
4. If multiple approaches exist, show the most common one first, then briefly note alternatives - draw a separator line, add a bold "Alternatives:" label, and then a numbered list of alternatives, with short explanation on the same line and the command on the next line (indented, inline code)

## Example output

Finds files in a directory tree matching a name pattern, optionally filtered by age.

```bash
find /var/log -name "*.log" -mtime -7
```
- `find /var/log` — starting directory to search
- `-name "*.log"` — match files ending in `.log`
- `-mtime -7` — modified within the last 7 days

---
**Alternatives:**
1. **locate** — faster for simple name searches (uses a pre-built index, may be stale)
   `locate "*.log"`
2. **fd** — modern alternative with simpler syntax
   `fd -e log . /var/log`

## Rules
- No "Sure!", "Here's how", or any opener beyond the one-line description
- No closing remarks or offers to explain further
- Always explain every flag, even obvious ones
- For destructive commands (`rm`, `chmod -R`, `dd`, etc.), add a one-line ⚠️ warning after the syntax breakdown

## Task
$ARGUMENTS
