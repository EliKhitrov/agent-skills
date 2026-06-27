#!/usr/bin/env python3
"""
render.py — Convert analysis.json + html-template.html → architecture.html

Usage:
    python render.py <report-dir> <template-path>

Reads:
    <report-dir>/analysis.json
    <report-dir>/analysis.meta.json

Writes:
    <report-dir>/architecture.html
"""

import html
import json
import re
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def fmt_duration(seconds):
    if seconds < 60:
        return f"{seconds}s"
    m, s = divmod(int(seconds), 60)
    return f"{m}m {s}s"


def tok_k(n, exact=False):
    val = f"{n / 1000:.1f}k"
    return val if exact else f"~{val}"


def fmt_cost_component(component, label):
    model = component.get("model", "unknown")
    exact = component.get("exact", False)
    in_k  = tok_k(component.get("input_tokens", 0), exact)
    out_k = tok_k(component.get("output_tokens", 0), exact)
    cost  = component.get("cost_usd", 0)
    return f"{label} ({model}): {in_k} in / {out_k} out · ≈ ${cost:.2f}"


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------

def build_invocation_ui(metadata):
    parts = []

    invocations = metadata.get("invocation", [])
    if isinstance(invocations, str):
        invocations = [invocations]
    parts.append(f'<pre>{html.escape(chr(10).join(invocations))}</pre>')

    input_formats = metadata.get("input_formats", [])
    desc = html.escape(metadata.get("input_description", ""))
    if input_formats:
        fmts = " ".join(f"<code>{html.escape(f)}</code>" for f in input_formats)
        parts.append(f"<p><strong>Input:</strong> {fmts}. {desc}</p>")
    elif desc:
        parts.append(f"<p><strong>Input:</strong> {desc}</p>")

    out_path = html.escape(metadata.get("output_path", ""))
    out_desc = html.escape(metadata.get("output_description", ""))
    if out_path or out_desc:
        parts.append(f"<p><strong>Output:</strong> <code>{out_path}</code> — {out_desc}</p>")

    flags = metadata.get("flags", [])
    if flags:
        flag_items = "".join(
            f"<li><code>{html.escape(f['flag'])}</code> — {html.escape(f['description'])}</li>"
            for f in flags
        )
        parts.append(
            f"<details style='margin-top:10px'>"
            f"<summary style='cursor:pointer;font-weight:600;color:var(--text)'>Flags</summary>"
            f"<ul style='margin:6px 0 0 1.2em;line-height:1.8'>{flag_items}</ul>"
            f"</details>"
        )

    return "\n".join(parts)


def build_pipeline_html(pipeline, actors):
    # Flatten phases → stages, keeping phase name alongside each stage
    flat = []
    for phase in pipeline:
        for stage in phase.get("stages", []):
            flat.append((phase["phase"], stage))

    total = len(flat)

    # Actor logic_type lookup for badge assignment
    actor_type_map = {
        a["name"]: a.get("logic_type", "Deterministic").lower()
        for a in actors
    }

    def stage_actor_type(stage):
        actor_name = stage.get("actor", "")
        lt = actor_type_map.get(actor_name, "")
        if lt == "llm":
            return "llm"
        if lt == "hybrid":
            return "hybrid"
        return "det"

    # Left column: vertical flow-chain of stage boxes
    chain_items = []
    for i, (phase_name, stage) in enumerate(flat):
        n = i + 1
        label = stage.get("label", stage.get("id", f"Stage {n}"))
        label_short = label[:50] + ("…" if len(label) > 50 else "")

        chain_items.append(
            f'<div class="flow-node">'
            f'<div class="flow-box stage" onclick="selectStage({i}, this)">'
            f'<span class="stage-name">{n} · {html.escape(phase_name)}</span>'
            f'<span class="stage-desc">— {html.escape(label_short)}</span>'
            f'</div></div>'
        )

        if i < total - 1:
            scripts = stage.get("scripts", [])
            ext     = stage.get("external_calls", [])
            connector = (scripts[0] if scripts else ext[0] if ext else "→")[:30]
            chain_items.append(
                f'<div class="flow-connector">{html.escape(connector)}</div>'
            )

    flow_chain = '<div class="flow-chain">\n' + "\n".join(chain_items) + "\n</div>"

    # Right column: static detail panel (JS fills it)
    detail_panel = (
        '<div class="stage-detail" id="sd-detail">\n'
        '  <div class="detail-num" id="sd-num"></div>\n'
        '  <div class="detail-title" id="sd-title"></div>\n'
        '  <div class="detail-row"><div class="detail-label">Actor</div>'
        '<div class="detail-value" id="sd-actor"></div></div>\n'
        '  <div class="detail-row"><div class="detail-label">Description</div>'
        '<div class="detail-value" id="sd-desc"></div></div>\n'
        '  <div class="detail-row" id="sd-row-model"><div class="detail-label">Model</div>'
        '<div class="detail-value" id="sd-model"></div></div>\n'
        '  <div class="detail-row" id="sd-row-scripts"><div class="detail-label">Scripts</div>'
        '<div class="detail-value" id="sd-scripts"></div></div>\n'
        '  <div class="detail-row" id="sd-row-ext"><div class="detail-label">External calls</div>'
        '<div class="detail-value" id="sd-ext"></div></div>\n'
        '</div>'
    )

    # pipelineStages JS array
    stage_objs = []
    for i, (phase_name, stage) in enumerate(flat):
        n = i + 1
        atype      = stage_actor_type(stage)
        scripts    = stage.get("scripts", [])
        ext        = stage.get("external_calls", [])
        actor_name = stage.get("actor", "")
        aid        = actor_id(actor_name) if actor_name else ""
        stage_objs.append(
            "  {"
            f' num: {json.dumps(f"Phase {n} of {total}")}, '
            f'title: {json.dumps(stage.get("label", phase_name))}, '
            f'actor: {json.dumps(actor_name)}, '
            f'actor_id: {json.dumps(aid)}, '
            f'actor_type: {json.dumps(atype)}, '
            f'desc: {json.dumps(stage.get("description", ""))}, '
            f'model: {json.dumps(stage.get("model"))}, '
            f'scripts: {json.dumps(scripts)}, '
            f'ext: {json.dumps(ext)}'
            " }"
        )

    stages_js = "[\n" + ",\n".join(stage_objs) + "\n]"

    script_block = f"""<script>
const pipelineStages = {stages_js};
const badgeMap = {{
  llm:    '<span class="badge badge-llm">LLM</span>',
  det:    '<span class="badge badge-det">Deterministic</span>',
  hybrid: '<span class="badge badge-hybrid">Hybrid</span>'
}};
function selectStage(i, el) {{
  document.querySelectorAll('.flow-box.stage').forEach(b => b.classList.remove('active'));
  el.classList.add('active');
  const s = pipelineStages[i];
  document.getElementById('sd-num').textContent = s.num;
  document.getElementById('sd-title').textContent = s.title;
  document.getElementById('sd-actor').innerHTML =
    (s.actor_id ? '<span class="tag tag-link" onclick="goActor(\\'' + s.actor_id + '\\')">' + s.actor + '</span>' : s.actor)
    + '\\u00a0\\u00a0' + (badgeMap[s.actor_type] || '');
  document.getElementById('sd-desc').textContent = s.desc;
  const rowModel   = document.getElementById('sd-row-model');
  const rowScripts = document.getElementById('sd-row-scripts');
  const rowExt     = document.getElementById('sd-row-ext');
  rowModel.style.display   = s.model ? '' : 'none';
  rowScripts.style.display = (s.scripts && s.scripts.length) ? '' : 'none';
  rowExt.style.display     = (s.ext && s.ext.length) ? '' : 'none';
  if (s.model) document.getElementById('sd-model').textContent = s.model;
  if (s.scripts && s.scripts.length)
    document.getElementById('sd-scripts').innerHTML =
      '<div class="tag-list">' + s.scripts.map(x => {{
        const sid = 'script-' + x.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
        return '<span class="tag tag-link" onclick="goScript(\\'' + sid + '\\')">' + x + '</span>';
      }}).join('') + '</div>';
  if (s.ext && s.ext.length)
    document.getElementById('sd-ext').innerHTML =
      '<div class="tag-list">' + s.ext.map(x => {{
        const id = 'dep-' + x.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
        return '<span class="tag tag-link" onclick="goDep(\\'' + id + '\\')">' + x + '</span>';
      }}).join('') + '</div>';
  const detail = document.getElementById('sd-detail');
  detail.classList.remove('visible');
  void detail.offsetWidth;
  detail.classList.add('visible');
}}
window.addEventListener('DOMContentLoaded', () => {{
  const first = document.querySelectorAll('.flow-box.stage')[0];
  if (first) selectStage(0, first);
}});
</script>"""

    return (
        '<div class="pipeline-layout">\n'
        + flow_chain + "\n"
        + detail_panel + "\n"
        + "</div>\n"
        + script_block
    )


def build_sequence_code(sequence):
    # Collect unique actor names for participant declarations
    seen = []
    for step in sequence:
        for key in ("from", "to"):
            name = step[key]
            if name not in seen:
                seen.append(name)

    lines = ["sequenceDiagram"]
    for name in seen:
        # Quote names that contain spaces
        quoted = f'"{name}"' if " " in name else name
        lines.append(f"  participant {quoted}")
    lines.append("")

    for step in sequence:
        frm = f'"{step["from"]}"' if " " in step["from"] else step["from"]
        to  = f'"{step["to"]}"'   if " " in step["to"]   else step["to"]
        msg = step["message"]
        # Strip characters that break Mermaid parser
        for ch in '"\'()[]{}':
            msg = msg.replace(ch, "")
        # Return messages use dashed arrow
        is_return = msg.lower().lstrip().startswith("return")
        arrow = "-->>" if is_return else "->>"
        lines.append(f"  {frm}{arrow}{to}: {msg}")

    return "\n".join(lines)


def build_implementation_map(actors, pipeline, artifacts, deps):
    # Collect unique scripts across all stages
    seen_scripts = set()
    scripts_ordered = []
    for phase in pipeline:
        for stage in phase.get("stages", []):
            for s in stage.get("scripts", []):
                if s not in seen_scripts:
                    seen_scripts.add(s)
                    scripts_ordered.append(s)

    def actor_dot(logic_type):
        lt = logic_type.lower()
        if lt == "llm":
            return "dot-llm"
        if lt == "hybrid":
            return "dot-hybrid"
        return "dot-det"

    col1 = "\n".join(
        f'<div class="impl-item impl-link" onclick="goActor(\'{actor_id(a["name"])}\')">'
        f'<div class="dot {actor_dot(a.get("logic_type","Deterministic"))}"></div>'
        f'<div><strong>{html.escape(a["name"])}</strong><br>'
        f'<span style="font-size:0.78rem;color:var(--muted)">{html.escape(a.get("logic_type",""))}</span>'
        f'</div></div>'
        for a in actors
    )

    script_items = "\n".join(
        f'<div class="impl-item impl-link" onclick="goScript(\'{script_id(s)}\')">'
        f'<div class="dot dot-det"></div>'
        f'<div><code>{html.escape(s)}</code></div></div>'
        for s in scripts_ordered
    ) or '<div class="impl-item"><div class="dot dot-det"></div><div>No scripts</div></div>'

    dep_items = "\n".join(
        f'<div class="impl-item impl-link" onclick="goDep(\'{dep_id(d["name"])}\')">'
        f'<div class="dot dot-ext"></div>'
        f'<div><code>{html.escape(d["name"])}</code></div></div>'
        for d in deps
    )
    col2 = script_items + (
        f'\n<div class="impl-col-sep">External calls</div>\n{dep_items}' if dep_items else ""
    )

    col3 = "\n".join(
        f'<div class="impl-item impl-link" onclick="goArt(\'{art_id(a.get("label",""))}\')">'
        f'<div class="dot dot-file"></div>'
        f'<div>{html.escape(a.get("label",""))}</div></div>'
        for a in artifacts
    )

    return (
        '<div class="impl-grid">\n'
        f'  <div class="impl-col"><h4>Actors</h4>{col1}</div>\n'
        f'  <div class="impl-col"><h4>Scripts</h4>{col2}</div>\n'
        f'  <div class="impl-col"><h4>Artifacts</h4>{col3}</div>\n'
        '</div>'
    )



def _clean_label(s):
    return re.sub(r'["\[\]{}()\'`]', '', str(s))[:40]


def _mermaid_activity_rich(ad, phase_data, expanded_set, actor_type_map):
    """Build Mermaid flowchart LR from the explicit activity_diagram node/edge schema."""
    raw_nodes = ad.get('nodes', [])
    raw_edges = ad.get('edges', [])
    node_map  = {n['id']: n for n in raw_nodes}
    phase_by_name = {p['name']: p for p in phase_data}

    collapsed_phases = {
        p['name'] for i, p in enumerate(phase_data)
        if p['collapsible'] and i not in expanded_set
    }
    expanded_coll = {
        p['name'] for i, p in enumerate(phase_data)
        if p['collapsible'] and i in expanded_set
    }
    collapsed_ids = {n['id'] for n in raw_nodes if n.get('phase') in collapsed_phases}

    # For each expanded collapsible phase, find which node IDs are entry points
    # (i.e. they receive an edge from outside their phase) so we can route those
    # edges through the phase header node instead.
    phase_entry_ids: dict = {}
    for e in raw_edges:
        to_ = e['to']
        if to_ in ('START', 'END'):
            continue
        to_n = node_map.get(to_)
        if not to_n:
            continue
        to_phase = to_n.get('phase')
        if to_phase not in expanded_coll:
            continue
        from_n = node_map.get(e['from'])
        from_phase = from_n.get('phase') if from_n else None
        if from_phase != to_phase:
            phase_entry_ids.setdefault(to_phase, set()).add(to_)

    node_lines, edge_lines, style_lines = [], [], []

    node_lines += ['  S(("▶"))', '  Z(("■"))']
    style_lines += [
        '  style S fill:#64ffda,stroke:#64ffda,color:#0f1117',
        '  style Z fill:#64ffda,stroke:#64ffda,color:#0f1117',
    ]

    for n in raw_nodes:
        if n['type'] == 'terminal_error':
            node_lines.append(f'  {n["id"]}(("✕"))')
            style_lines.append(f'  style {n["id"]} fill:#3a1010,stroke:#ff5555,color:#ff5555')

    for i, phase in enumerate(phase_data):
        if not phase['collapsible']:
            continue
        pid, pname = phase['node_id'], phase['name']
        if i in expanded_set:
            node_lines.append(f'  {pid}["▾ {_clean_label(pname)}"]')
            style_lines.append(f'  style {pid} fill:#1d2f42,stroke:#4da6d6,color:#aad4e8')
        else:
            node_lines.append(f'  {pid}["📦 {_clean_label(pname)} · {phase["stage_count"]} steps"]')
            style_lines.append(f'  style {pid} fill:#152535,stroke:#4da6d6,color:#7ec8e3')

    for n in raw_nodes:
        nid = n['id']
        if n['type'] == 'terminal_error' or nid in collapsed_ids:
            continue
        label = _clean_label(n.get('label', nid))
        if n['type'] == 'decision':
            node_lines.append(f'  {nid}{{"{label}"}}')
        else:
            node_lines.append(f'  {nid}["{label}"]')
        if actor_type_map.get(n.get('actor', ''), '') == 'llm':
            style_lines.append(f'  style {nid} fill:#251535,stroke:#c792ea,color:#d4a5f5')

    seen: set = set()

    def add_edge(frm, to_, lbl=''):
        key = (frm, to_, lbl)
        if key in seen:
            return
        seen.add(key)
        if lbl:
            edge_lines.append(f'  {frm} -- {lbl} --> {to_}')
        else:
            edge_lines.append(f'  {frm} --> {to_}')

    for e in raw_edges:
        frm, to_, lbl = e['from'], e['to'], (e.get('label') or '').strip()
        eff_from = 'S' if frm == 'START' else frm
        eff_to   = 'Z' if to_ == 'END'   else to_

        from_n    = node_map.get(frm)
        to_n      = node_map.get(to_)
        from_phase = from_n.get('phase') if from_n else None
        to_phase   = to_n.get('phase')   if to_n   else None

        if from_phase in collapsed_phases:
            eff_from = phase_by_name[from_phase]['node_id']
        if to_phase in collapsed_phases:
            eff_to = phase_by_name[to_phase]['node_id']

        # Skip edges internal to a collapsed phase
        if frm in collapsed_ids and to_ in collapsed_ids and from_phase == to_phase:
            continue

        # Intercept edges entering an expanded collapsible phase → route via header
        if (to_phase in expanded_coll
                and to_ in phase_entry_ids.get(to_phase, set())
                and from_phase != to_phase):
            pid = phase_by_name[to_phase]['node_id']
            add_edge(eff_from, pid, lbl)
            add_edge(pid, eff_to)
            continue

        add_edge(eff_from, eff_to, lbl)

    return 'flowchart LR\n' + '\n'.join(node_lines + edge_lines + style_lines)


def _mermaid_activity_state(phase_data, expanded_set):
    """Build a Mermaid flowchart LR string for the given set of expanded phase indices."""
    lines = ['flowchart LR', '  S(("▶"))']
    prev_id = 'S'

    for pi, phase in enumerate(phase_data):
        expanded = pi in expanded_set
        if phase['collapsible'] and not expanded:
            lines.append(f'  {phase["node_id"]}["📦 {_clean_label(phase["name"])} · {phase["stage_count"]} steps"]')
            lines.append(f'  {prev_id} --> {phase["node_id"]}')
            prev_id = phase['node_id']
        else:
            if phase['collapsible']:
                lines.append(f'  {phase["node_id"]}["▾ {_clean_label(phase["name"])}"]')
                lines.append(f'  {prev_id} --> {phase["node_id"]}')
                prev_id = phase['node_id']
            for stage in phase['stages']:
                nid, label = stage['node_id'], _clean_label(stage['label'])
                lines.append(f'  {nid}["{label}"]')
                lines.append(f'  {prev_id} --> {nid}')
                prev_id = nid

    lines += ['  Z(("■"))', f'  {prev_id} --> Z',
              '  style S fill:#64ffda,stroke:#64ffda,color:#0f1117',
              '  style Z fill:#64ffda,stroke:#64ffda,color:#0f1117']

    for pi, phase in enumerate(phase_data):
        if phase['collapsible']:
            c = '#1d2f42,stroke:#4da6d6,color:#aad4e8' if pi in expanded_set else '#152535,stroke:#4da6d6,color:#7ec8e3'
            lines.append(f'  style {phase["node_id"]} fill:{c}')
        if pi in expanded_set or not phase['collapsible']:
            for stage in phase['stages']:
                if stage.get('logic_type') == 'llm':
                    lines.append(f'  style {stage["node_id"]} fill:#251535,stroke:#c792ea,color:#d4a5f5')

    return '\n'.join(lines)


def build_activity_diagram_data(pipeline, actors, activity_diagram=None):
    """Pre-compute all collapse/expand state diagrams and return as a JSON string."""
    actor_type_map = {
        a['name']: a.get('logic_type', 'Deterministic').lower()
        for a in actors
    }
    used_ids: set = set()

    def make_node_id(s, prefix='N'):
        base = re.sub(r'[^A-Za-z0-9]', '', s.upper()) or prefix
        if not base[0].isalpha():
            base = prefix + base
        base = base[:12]
        nid, i = base, 0
        while nid in used_ids:
            i += 1
            nid = base[:10] + str(i)
        used_ids.add(nid)
        return nid

    phase_data = []
    for pi, phase in enumerate(pipeline):
        stages = phase.get('stages', [])
        stage_data = []
        for si, stage in enumerate(stages):
            nid = make_node_id(stage.get('id', f'stage{pi}{si}'), 'S')
            actor_name = stage.get('actor', '')
            lt = actor_type_map.get(actor_name, 'deterministic')
            if stage.get('model'):
                lt = 'llm'
            label = re.sub(r'["\[\]{}()\'`]', '', stage.get('label', nid))[:40]
            stage_data.append({'node_id': nid, 'label': label, 'logic_type': lt})

        phase_data.append({
            'name': phase['phase'],
            'node_id': make_node_id(phase['phase'], 'P'),
            'collapsible': len(stages) >= 2,
            'stage_count': len(stages),
            'stages': stage_data,
        })

    collapsible = [(pi, p) for pi, p in enumerate(phase_data) if p['collapsible']]
    n_bits = len(collapsible)

    use_rich = bool(activity_diagram and activity_diagram.get('nodes'))
    diagrams = {}
    for state in range(2 ** n_bits):
        expanded_set = {pi for bit, (pi, _) in enumerate(collapsible) if state & (1 << bit)}
        if use_rich:
            diagrams[str(state)] = _mermaid_activity_rich(
                activity_diagram, phase_data, expanded_set, actor_type_map
            )
        else:
            diagrams[str(state)] = _mermaid_activity_state(phase_data, expanded_set)

    return json.dumps({
        'diagrams': diagrams,
        'collapsible': [
            {'bit': 1 << bit, 'name': phase_data[pi]['name']}
            for bit, (pi, _) in enumerate(collapsible)
        ],
        'all_expanded': (2 ** n_bits) - 1,
    })


def build_actors_table(actors):
    def badge(logic_type):
        lt = logic_type.lower()
        if lt == "llm":
            return '<span class="badge badge-llm">LLM</span>'
        if lt == "hybrid":
            return '<span class="badge badge-hybrid">Hybrid</span>'
        return '<span class="badge badge-det">Deterministic</span>'

    rows = []
    for a in actors:
        rows.append(
            f'<tr id="{actor_id(a["name"])}">'
            f'<td><strong>{html.escape(a["name"])}</strong></td>'
            f'<td>{badge(a.get("logic_type","Deterministic"))}</td>'
            f'<td>{html.escape(a.get("model_assignment","n/a"))}</td>'
            f'<td>{html.escape(a.get("responsibility",""))}</td>'
            f'</tr>'
        )
    return "\n".join(rows)


def build_artifacts_html(artifacts, has_rr):
    cols = 6 if has_rr else 5
    risk_th = '<th style="width:10%">Risk</th>' if has_rr else ""
    rows = []
    for a in artifacts:
        risk      = a.get("privacy_risk", "low")
        durable   = "Yes" if a.get("is_durable") else "No"
        consumers = html.escape(", ".join(a.get("consumers", [])))
        schema    = html.escape(a.get("schema_ref") or "—")
        risk_td   = f'<td><span class="risk-{risk}">{risk}</span></td>' if has_rr else ""
        desc      = html.escape(a.get("description", "") or "").strip()
        path      = html.escape(a.get("path_pattern") or "")

        # Specific script names for producer/consumer
        ps = a.get("producer_script")
        producer_html = html.escape(a.get("producer", ""))
        if ps:
            psid = script_id(ps)
            producer_html += f' <span class="tag tag-link" onclick="goScript(\'{psid}\')" style="font-size:0.82em">{html.escape(ps)}</span>'

        cs = a.get("consumer_scripts") or []
        if cs:
            # Replace "Scripts" actor entries with actual script names
            consumer_parts = []
            script_queue = list(cs)
            for c in a.get("consumers", []):
                if c == "Scripts" and script_queue:
                    cs_name = script_queue.pop(0)
                    consumer_parts.append(f'<span class="tag tag-link" onclick="goScript(\'{script_id(cs_name)}\')" style="font-size:0.82em">{html.escape(cs_name)}</span>')
                else:
                    consumer_parts.append(html.escape(c))
            consumers = ", ".join(consumer_parts)

        detail_html = (
            f'<div class="artifact-detail">'
            + (f'<p>{desc}</p>' if desc else '<p style="color:var(--muted);font-style:italic">No description available.</p>')
            + (f'<p style="margin-top:10px"><strong>Path:</strong> <code>{path}</code></p>' if path else "")
            + "</div>"
        )

        row_id = art_id(a.get("label", ""))
        rows.append(
            f'<tr class="artifact-row" id="{row_id}" onclick="toggleArtifact(this)">'
            f'<td><code>{html.escape(a.get("label",""))}</code></td>'
            f'<td>{producer_html}</td>'
            f'<td>{consumers}</td>'
            f'<td>{durable}</td>'
            f'{risk_td}'
            f'<td>{schema}</td>'
            f'</tr>'
            f'<tr class="artifact-expand">'
            f'<td colspan="{cols}">{detail_html}</td>'
            f'</tr>'
        )

    return (
        f'<table style="table-layout:fixed;width:100%">'
        f'<thead><tr>'
        f'<th style="width:18%">Artifact</th>'
        f'<th style="width:22%">Producer</th>'
        f'<th style="width:22%">Consumers</th>'
        f'<th style="width:10%">Durable</th>'
        f'{risk_th}<th>Schema</th>'
        f'</tr></thead>'
        f'<tbody>' + "\n".join(rows) + '</tbody>'
        f'</table>'
    )


def dep_id(name):
    return "dep-" + re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def art_id(label):
    return "art-" + re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")


def script_id(name):
    return "script-" + re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def actor_id(name):
    return "actor-" + re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def build_dependencies_list(deps):
    return "\n".join(
        f'<div class="card" id="{dep_id(d["name"])}"><h4>{html.escape(d["name"])}</h4>'
        f'<p>{html.escape(d.get("purpose",""))}</p></div>'
        for d in deps
    )


def build_scripts_html(scripts, pipeline, artifacts, deps):
    if not scripts:
        return "<p style='color:var(--muted)'>No scripts identified.</p>"

    script_phase = {}
    script_ext = {}
    for phase in pipeline:
        for stage in phase.get("stages", []):
            for s in stage.get("scripts", []):
                script_phase.setdefault(s, phase["phase"])
                for e in stage.get("external_calls", []):
                    if e not in script_ext.get(s, []):
                        script_ext.setdefault(s, []).append(e)

    script_reads = {}
    script_writes = {}
    for a in artifacts:
        ps = a.get("producer_script")
        if ps:
            script_writes.setdefault(ps, []).append(a.get("label", ""))
        for cs in (a.get("consumer_scripts") or []):
            script_reads.setdefault(cs, []).append(a.get("label", ""))

    def art_tags(labels):
        if not labels:
            return '<span style="color:var(--muted)">—</span>'
        return '<div class="tag-list">' + "".join(
            f'<span class="tag tag-link" onclick="goArt(\'{art_id(lbl)}\')">{html.escape(lbl)}</span>'
            for lbl in labels
        ) + "</div>"

    def ext_tags(calls):
        if not calls:
            return '<span style="color:var(--muted)">—</span>'
        return '<div class="tag-list">' + "".join(
            f'<span class="tag tag-link" onclick="goDep(\'{dep_id(e)}\')">{html.escape(e)}</span>'
            for e in calls
        ) + "</div>"

    rows = []
    for s in scripts:
        name    = s.get("name", "")
        purpose = html.escape(s.get("purpose", ""))
        sid     = script_id(name)
        phase   = html.escape(script_phase.get(name, "—"))

        reads_html  = art_tags(script_reads.get(name, []))
        writes_html = art_tags(script_writes.get(name, []))
        ext_html    = ext_tags(script_ext.get(name, []))

        no_purpose = '<span style="color:var(--muted);font-style:italic">No description.</span>'
        detail_html = (
            f'<div class="script-detail">'
            f'<p>{purpose or no_purpose}</p>'
            f'</div>'
        )

        rows.append(
            f'<tr class="script-row" id="{sid}" onclick="toggleScript(this)">'
            f'<td><code>{html.escape(name)}</code></td>'
            f'<td>{phase}</td>'
            f'<td>{reads_html}</td>'
            f'<td>{writes_html}</td>'
            f'<td>{ext_html}</td>'
            f'</tr>'
            f'<tr class="script-expand">'
            f'<td colspan="5">{detail_html}</td>'
            f'</tr>'
        )

    return (
        '<table style="table-layout:fixed;width:100%">'
        '<thead><tr>'
        '<th style="width:22%">Script</th>'
        '<th style="width:12%">Phase</th>'
        '<th style="width:22%">Input</th>'
        '<th style="width:22%">Output</th>'
        '<th style="width:22%">External tools</th>'
        '</tr></thead>'
        '<tbody>' + "\n".join(rows) + '</tbody>'
        '</table>'
    )


def build_rr_sections(analysis):
    resilience      = analysis.get("resilience")
    security        = analysis.get("security")
    recommendations = analysis.get("recommendations")

    if not resilience and not security and not recommendations:
        return "", ""

    button = '<div class="tab" onclick="show(\'risks\',this)">⚠️ Risks &amp; Resilience</div>'

    parts = ['<div id="risks" class="panel">']

    if resilience:
        fps = resilience.get("failure_points", [])
        cps = resilience.get("checkpoints", [])
        tn  = resilience.get("test_notes", "")
        if fps:
            lis = "\n".join(f"<li>{html.escape(x)}</li>" for x in fps)
            parts.append(f'<section><h3>Failure Points</h3><div class="risk-card"><ul>{lis}</ul></div></section>')
        if cps:
            lis = "\n".join(f"<li>{html.escape(x)}</li>" for x in cps)
            parts.append(f'<section><h3>Checkpoints</h3><ul class="checkpoint-list">{lis}</ul></section>')
        if tn:
            parts.append(f'<section><h3>Test Coverage</h3><p>{html.escape(tn)}</p></section>')

    if security:
        pn   = security.get("privacy_notes", "")
        vuls = security.get("vulnerabilities", [])
        if pn:
            parts.append(f'<section><h3>Privacy</h3><p>{html.escape(pn)}</p></section>')
        if vuls:
            lis = "\n".join(f"<li>{html.escape(x)}</li>" for x in vuls)
            parts.append(f'<section><h3>Vulnerabilities</h3><div class="risk-card"><ul>{lis}</ul></div></section>')

    if recommendations:
        if isinstance(recommendations, list):
            lis = "\n".join(f"<li>{html.escape(x)}</li>" for x in recommendations)
            parts.append(f'<section><h3>Recommendations</h3><div class="risk-card"><ul>{lis}</ul></div></section>')

    parts.append("</div>")
    return button, "\n".join(parts)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) < 3:
        print("Usage: render.py <report-dir> <template-path>", file=sys.stderr)
        sys.exit(1)

    report_dir    = Path(sys.argv[1])
    template_path = Path(sys.argv[2])
    output_path   = report_dir / "architecture.html"

    with open(report_dir / "analysis.json",      encoding="utf-8") as f:
        analysis = json.load(f)
    with open(report_dir / "analysis.meta.json", encoding="utf-8") as f:
        meta = json.load(f)
    with open(template_path,                     encoding="utf-8") as f:
        template = f.read()

    metadata  = analysis["metadata"]
    actors    = analysis.get("actors", [])
    pipeline  = analysis.get("pipeline", [])
    sequence  = analysis.get("sequence", [])
    artifacts = analysis.get("artifacts", [])
    deps      = analysis.get("external_dependencies", [])

    orch_meta = meta.get("orchestrator", {})
    sub_meta  = meta.get("subagent", {})
    rr_button, rr_panel = build_rr_sections(analysis)

    replacements = {
        "{{SKILL_NAME}}":        html.escape(metadata.get("name", "")),
        "{{SKILL_DESC}}":        html.escape(metadata.get("description", "")),
        "{{GENERATED_AT}}":      html.escape(meta.get("generated_at", "")),
        "{{DURATION}}":          fmt_duration(meta.get("duration_seconds", 0)),
        "{{ORCHESTRATOR_COST}}": fmt_cost_component(orch_meta, "Orchestrator"),
        "{{SUBAGENT_COST}}":     fmt_cost_component(sub_meta, "Analysis Subagent"),
        "{{TOTAL_COST}}":        f"≈ ${meta.get('total_cost_usd', 0):.2f}",
        "{{INVOCATION_UI}}":     build_invocation_ui(metadata),
        "{{PIPELINE_HTML}}":     build_pipeline_html(pipeline, actors),
        "{{SEQUENCE_CODE}}":     build_sequence_code(sequence),
        "{{IMPLEMENTATION_MAP}}": build_implementation_map(actors, pipeline, artifacts, deps),
        "{{ACTORS_TABLE}}":      build_actors_table(actors),
        "{{ARTIFACTS_TABLE_HTML}}": build_artifacts_html(artifacts, meta.get("has_rr", False)),
        "{{SCRIPTS_TABLE_HTML}}": build_scripts_html(
            analysis.get("scripts", []), pipeline, artifacts, deps
        ),
        "{{DEPENDENCIES_LIST}}": build_dependencies_list(deps),
        "{{ACTIVITY_DIAGRAM_DATA}}": build_activity_diagram_data(
            pipeline, actors, analysis.get("activity_diagram")
        ),
        "{{RR_TAB_BUTTON}}":     rr_button,
        "{{RR_TAB_PANEL}}":      rr_panel,
    }

    out = template
    for placeholder, value in replacements.items():
        out = out.replace(placeholder, value)

    # Warn about any unfilled placeholders
    import re
    remaining = re.findall(r'\{\{[A-Z_]+\}\}', out)
    if remaining:
        print(f"Warning: unfilled placeholders: {set(remaining)}", file=sys.stderr)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(out)

    print(f"Written: {output_path}")


if __name__ == "__main__":
    main()
