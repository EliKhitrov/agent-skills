---
name: analyse-skill
description: "Analyze any OpenClaw skill and render a comprehensive architecture report with split diagrams, risk analysis, and artifact tracking."
metadata:
  openclaw:
    emoji: "🏗️"
user-invocable: true
---

# Skill Architect

Analyzes a skill's full file tree and generates a multi-tab architecture report.

## Usage

```
/skill analyse-skill narrate-interview
/skill analyse-skill skills/my-custom-skill
/skill analyse-skill narrate-interview --rr
```

Flag `--rr` enables the **Risks & Resilience** tab (failure points, checkpoints, security, recommendations).
Without `--rr`, the R&R tab is omitted and the analyzer skips that analysis entirely (saves tokens).

## Output

Produces `<workspace>/reports/architecture/<skill-name>/architecture.html` containing:
- **Overview** — invocation interface + pipeline phase diagram (with edge labels)
- **Diagrams** — implementation map (HTML grid) + actor sequence (Mermaid)
- **Artifacts** — data lifecycle (HTML flow chain) + artifact registry table
- **Agents & Logic** — actor/model/responsibility table + external dependencies
- **Risks & Resilience** *(if `--rr`)* — failure points, checkpoints, security, recommendations

## Workflow

### Step 1 — Parse Arguments

Record `run_start` = current wall-clock time (ISO timestamp or epoch ms). This is the timer for the full run duration.

- Extract skill path/name and check for `--rr` flag. Set `include_rr = true/false`.
- If argument is a plain name, look for `skills/<name>` in the workspace root.
- Accept workspace-relative or absolute paths.
- Abort with a clear message if path not found.

### Step 2 — Scan

Use `find <skill-dir> -type f` to enumerate all files.

Collect **paths only** — do not read file content. Apply the following filter:

**Include paths matching:**
- `SKILL.md`
- `agents/*.md`
- `scripts/*.py`, `*.js`, `*.mjs`, `*.sh`
- `schemas/*.json`
- `references/*.md`

**Exclude paths under:**
- `models/`, `media/`, `jobs/`, `output/`, `readme/`
- `<workspace>/reports/`
- `.venv/`, `__pycache__/`, `.git/`, `.openclaw/`, `node_modules/`

The result is a curated list of file paths — nothing is read into the orchestrator's context.

Record `input_chars` = sum of file sizes in bytes across all collected paths (a cost estimate only; the orchestrator does not hold the content).

### Step 3 — Check Cache

Report output dir: `<workspace>/reports/architecture/<skill-name>/`

Check for `<report-dir>/analysis.meta.json`. If it exists:

```bash
find <skill-dir> -type f \
  -not -path "*/models/*" \
  -not -path "*/.venv/*" \
  -not -path "*/__pycache__/*" \
  -not -path "*/.git/*" \
  -not -path "*/.openclaw/*" \
  -newer <report-dir>/analysis.meta.json
```

- If no files are returned → source is unchanged since last analysis.
  - Read `<report-dir>/analysis.meta.json` to check `has_rr`.
  - If `include_rr = false` OR (`include_rr = true` AND `has_rr = true`) → **cache hit**: skip Step 4, load `<report-dir>/analysis.json` directly.
  - If `include_rr = true` AND `has_rr = false` → **partial miss**: set `rr_only = true`, proceed to Step 4 with only R&R analysis.
- If files were returned → **cache miss**: proceed to Step 4 with full analysis.

### Step 4 — Analyze

<!-- TODO: replace the model selection below with a dedicated model-selection skill
     once it exists — so all skills can share one canonical way to pick the right model. -->

Spawn a subagent using a **mid-tier reasoning model**: capable of structured JSON
extraction from multi-file codebases, nuanced architectural pattern recognition, and
producing ~3k-token JSON outputs reliably. Do not use the maximum-capability tier
(Opus-class) — unnecessarily expensive for this task. Do not use the fast/small tier
(Haiku-class) — it misses architectural nuance. As of June 2026, this corresponds to
Sonnet-class from Anthropic, GPT-4o-class from OpenAI, or the equivalent mid-tier from
whichever provider is active.

Use instructions from `agents/analyzer.md`.

Pass the following as the task body (the subagent reads the files itself — do not pre-load content):

```
INCLUDE_RR: true|false
SKILL_DIR: <absolute path to skill directory>
FILES:
  <absolute path 1>
  <absolute path 2>
  ...
TRUNCATE_LINES: 300
```

- `FILES` is the curated path list from Step 2, one path per line.
- `TRUNCATE_LINES: 300` instructs the subagent to read at most 300 lines per file and append `[truncated]` if the file exceeds 500 lines.

If `rr_only = true`, add `RR_ONLY: true` to the task body and instruct the subagent to return only the R&R fields (`resilience`, `security`, `recommendations`) to be merged into the existing `<report-dir>/analysis.json`.

The subagent reads each file, analyzes the content, and returns a single JSON block.

**After receiving the result:**

Record `run_end` = current wall-clock time.
- `duration_seconds` = elapsed seconds between `run_start` and `run_end` (integer).
- `output_json_chars` = character count of the raw JSON string returned by the subagent.

**Subagent token counts** — use the most accurate source available:
- **If** the subagent response includes a `usage` object with `input_tokens` and
  `output_tokens` → use those exact values (`sub_in_exact = true`).
- **Else** → estimate: `sub_in` = round(`input_chars` / 4);
  `sub_out` = round(`output_json_chars` / 4); `sub_in_exact = false`.

**Orchestrator token counts** (always estimated via chars / 4):
- `orch_in` = round(`output_json_chars` / 4)
  *(the orchestrator's context holds the subagent's JSON response only — file content is never loaded into the orchestrator)*
- `orch_out` = round(HTML file character count / 4)
  *(measured after Step 6 writes the report)*
- `orch_model` = model running the current session, if determinable from context; otherwise `"unknown"`.

**Pricing table** (hardcoded, USD per 1M tokens):

| Model family | Input $/MTok | Output $/MTok |
|---|---|---|
| `sonnet` / `claude-sonnet-*` | 3.00 | 15.00 |
| `opus` / `claude-opus-*` | 15.00 | 75.00 |
| `haiku` / `claude-haiku-*` | 0.80 | 4.00 |
| `unknown` | 3.00 | 15.00 *(sonnet-class assumption)* |

Compute costs using the appropriate row for each component's model.

Create `<workspace>/reports/architecture/<skill-name>/` if missing.
Write full JSON to `<report-dir>/analysis.json`.
Write cache meta to `<report-dir>/analysis.meta.json`:

```json
{
  "generated_at": "<ISO timestamp>",
  "has_rr": false,
  "skill_path": "<absolute path>",
  "duration_seconds": 42,
  "orchestrator": {
    "model": "sonnet",
    "input_tokens": 12400,
    "output_tokens": 3800,
    "cost_usd": 0.094,
    "exact": false
  },
  "subagent": {
    "model": "sonnet",
    "input_tokens": 9800,
    "output_tokens": 2100,
    "cost_usd": 0.061,
    "exact": true
  },
  "total_cost_usd": 0.155
}
```

Touch `analysis.meta.json` last (after all other writes) so its mtime is the watermark for `find -newer`.

### Step 5 — Render HTML

Run the render script to convert `analysis.json` + `analysis.meta.json` into `architecture.html`:

```bash
python <skill-dir>/scripts/render.py <report-dir> <skill-dir>/references/html-template.html
```

- `<skill-dir>` = the `analyse-skill` directory (not the target skill).
- `<report-dir>` = `<workspace>/reports/architecture/<skill-name>/`

The script reads `<report-dir>/analysis.json` and `<report-dir>/analysis.meta.json`, fills all template placeholders, and writes `<report-dir>/architecture.html`. It exits non-zero and prints an error if any required file is missing.

If the script is not available (OpenClaw environment without Python), fall back to manual placeholder substitution following the rules in `scripts/render.py` (all builder functions are documented inline).

### Step 6 — Show Result

- Print the path to the generated HTML.
- In WebChat: copy to `~/.openclaw/canvas/<skill-name>-arch.html` and embed with `[embed ...]`.

## Mermaid Safety Rules

- Use Mermaid **only** for the sequence diagram.
  Pipeline overview, implementation map, and data lifecycle all use HTML (no parsing, no layout failures).
- Sanitize all Mermaid labels: no `"` `'` `(` `)` `[` `]` `{` `}` `.` in unquoted positions.
- Use double-quoted labels for anything with dots: `SC1["extract_transcript_text.py"]`
- Keep the pipeline diagram flat — no subgraphs.
- `startOnLoad: false` is set in the template; each panel initializes lazily on first tab click.

## Boundaries

- Skip `models/` when scanning; never scan or write into another skill's `readme/`.
- Max 300 lines per file; truncate with `[truncated]`.
- If no subagents, sequence uses `Orchestrator` and `User` only.
