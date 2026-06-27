# Skill Architecture Analyzer

Your task body contains control directives and a list of file paths. Read each file yourself, then extract structured architecture metadata and return it as **one JSON block only**. No prose before or after it.

## Task body format

```
INCLUDE_RR: true|false
SKILL_DIR: <absolute path>
FILES:
  <absolute path 1>
  <absolute path 2>
  ...
TRUNCATE_LINES: 300
```

Optional:
```
RR_ONLY: true
```

## Reading instructions

- Read every file listed under `FILES` using your file-reading tool.
- If a file exceeds 500 lines, read only the first 300 lines and treat the remainder as `[truncated]`.
- If a file cannot be read, note it in `warnings` and continue.

## Output instructions

If `INCLUDE_RR: false`, omit the `resilience`, `security`, and `recommendations` fields entirely — do not analyze them.
If `INCLUDE_RR: true`, include all fields.
If `RR_ONLY: true`, return only the R&R fields (`resilience`, `security`, `recommendations`) — omit all other top-level keys.

## Output Format

Return exactly:

```json
{ ... }
```

No other text. The JSON must be valid and match the schema below.

## Base Schema (always returned)

```json
{
  "metadata": {
    "name": "string — from SKILL.md name field",
    "description": "string — one-line description of what the skill does",
    "invocation": "string[] — one or more example CLI/slash command lines (e.g. [\"/skill narrate-interview transcript.pdf\", \"/skill narrate-interview interview.md --style formal\"])",
    "input_formats": "string[] — accepted input file extensions or types (e.g. [\".txt\", \".md\", \".pdf\"]), or empty array if skill takes no file input",
    "input_description": "string — one sentence describing what the user passes in (e.g. 'Interview transcript file path and optional narration preferences')",
    "output_path": "string — output file path pattern (e.g. workspace/narrations/jobs/<timestamp>/interview_narration.mp3)",
    "output_description": "string — one sentence describing what the skill produces",
    "flags": [
      { "flag": "--flag-name", "description": "what it enables or changes" }
    ],
    "user_interface": "Description of how the user interacts with this skill (CLI, WebChat, etc.)"
  },
  "actors": [
    {
      "name": "string",
      "role": "Short role label",
      "responsibility": "Detailed responsibility description",
      "logic_type": "LLM | Deterministic | Hybrid",
      "model_assignment": "Model alias, 'default model', or 'n/a'"
    }
  ],
  "pipeline": [
    {
      "phase": "string (e.g. Discovery, Extraction, Analysis, Narration, Rendering, Output)",
      "stages": [
        {
          "id": "stage_id",
          "label": "Human-readable label (max 35 chars, no special chars)",
          "actor": "actor_name",
          "description": "What happens in this stage",
          "model": "Model name/alias, or null if not LLM",
          "scripts": ["script filenames"],
          "external_calls": ["CLI tools or APIs called"]
        }
      ]
    }
  ],
  "sequence": [
    {
      "from": "actor_name",
      "to": "actor_name",
      "message": "High-level action description (no special chars)"
    }
  ],
  "artifacts": [
    {
      "label": "Short label (no special chars, no dots)",
      "description": "2-4 sentence description: what the artifact contains, what format/structure it has, and why it exists in the pipeline",
      "path_pattern": "File path or glob pattern",
      "producer": "actor_name",
      "producer_script": "specific script filename if producer is a script runner, else null",
      "consumers": ["actor_name"],
      "consumer_scripts": ["specific script filenames that consume this artifact — only if consumers include a script runner, else empty array"],
      "is_durable": true,
      "privacy_risk": "low | medium | high",
      "schema_ref": "Path to schema file or null"
    }
  ],
  "scripts": [
    {
      "name": "script filename (e.g. extract_transcript_text.py)",
      "purpose": "One sentence describing exactly what this script does — be specific about inputs, transformation, and outputs"
    }
  ],
  "external_dependencies": [
    {
      "name": "string",
      "purpose": "Start with the technology type (e.g. 'CLI tool', 'Python module', 'native binary', 'client-side JS library', 'REST API', 'system daemon'), then describe what role it plays in this skill and any relevant runtime conditions (how it is located, what happens if missing, environment variables it needs). 2-3 sentences max."
    }
  ],
  "activity_diagram": {
    "nodes": [
      {
        "id": "Short uppercase alphanumeric ID, max 8 chars, unique across all nodes (e.g. PF, ERR, SF, CV). No spaces or special chars.",
        "type": "action | decision | terminal_error",
        "label": "Human-readable label, max 35 chars, no special chars",
        "phase": "Must exactly match a phase name from the pipeline array. Set to null only for terminal_error nodes that fall outside any phase.",
        "actor": "Actor name from the actors array, or null"
      }
    ],
    "edges": [
      {
        "from": "Node id, or the reserved keyword START (the entry point of the skill)",
        "to": "Node id, or the reserved keyword END (successful completion)",
        "label": "Condition label for decision branches (e.g. Yes, No, Hit, Miss, Partial), or null for unconditional flow"
      }
    ]
  }
}
```

## R&R Schema (only when INCLUDE_RR: true — append to the base JSON)

```json
{
  "resilience": {
    "failure_points": ["Specific points where the skill might fail"],
    "checkpoints": ["Points where the skill can resume or retry"],
    "test_notes": "Existing test coverage or notable gaps"
  },
  "security": {
    "privacy_notes": "Notes on data handling and privacy",
    "vulnerabilities": ["Potential security risks"]
  },
  "recommendations": ["Architectural improvement suggestions"]
}
```

## Instructions

- Infer actor names from agent file names, SKILL.md descriptions, and `sessions_spawn` calls.
- Group stages into high-level phases based on the workflow execution order.
- Identify Deterministic (scripts/shell) vs LLM (agent prompts) vs Hybrid logic.
- For artifacts, distinguish temporary intermediate files from durable outputs.
- **Sanitize all labels and messages**: no `"` `'` `(` `)` `[` `]` `{` `}` — these break Mermaid. Use plain words.
- If a model is not explicitly stated for an LLM actor, write `"default model"`.
- Identify external_calls from subprocess calls, shutil.which checks, and CLI tool references.
- For sequence, use only high-level actors: User, Orchestrator, LLM agent names, Scripts, FileSystem.
- For `activity_diagram` — this is the primary visual representation of the skill's flow and must be thorough:
  - Every stage in `pipeline` must appear as an `action` node (one node per stage, using the stage label).
  - Add `decision` nodes for every branching point: flag checks, file existence, cache validity, mode switches, retry logic, format detection, etc. These are diamonds in the diagram.
  - Add `terminal_error` nodes for hard-failure or abort paths (e.g. "path not found", "invalid input"). These receive edges but have no outgoing edge to END.
  - Include bypass or shortcut edges — e.g. a cache-hit that skips an entire phase and jumps directly to a later phase.
  - Set `actor` on every node — this drives LLM-stage highlighting (purple) in the rendered report.
  - Node IDs must be globally unique short abbreviations (PF = Path Found check, CV = Cache Valid check, SF = Scan Files action, ERR = abort terminal).
  - `phase` must exactly match a phase name from the `pipeline` array (case-sensitive).
  - Every non-terminal node must have at least one outgoing edge. The graph must be connected from START to END (and/or terminal_error nodes).
