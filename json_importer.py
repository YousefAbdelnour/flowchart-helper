from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from flowchart_model import (
    EdgeKind,
    FlowDirection,
    FlowEdge,
    FlowGraph,
    FlowNode,
    FlowNodeType,
    Step,
    StepType,
    ValidationIssue,
    validate_graph,
)


class JsonImportError(ValueError):
    pass


@dataclass(frozen=True)
class ParsedFlowchart:
    title: str
    steps: list[Step]
    metadata: dict[str, str]
    graph: FlowGraph | None = None
    issues: list[ValidationIssue] | None = None
    is_graph_json: bool = False

    @property
    def error_issues(self) -> list[ValidationIssue]:
        return [issue for issue in self.issues or [] if issue.severity == "error"]

    @property
    def warning_issues(self) -> list[ValidationIssue]:
        return [issue for issue in self.issues or [] if issue.severity == "warning"]


JSON_EXAMPLE = """{
  "version": "1.0",
  "title": "A Basic Flowchart",
  "nodes": [
    { "id": "start", "type": "start", "text": "Start" },
    { "id": "step", "type": "process", "text": "Step" },
    { "id": "decision", "type": "decision", "text": "Decision?" },
    { "id": "yes_action", "type": "action", "text": "Action" },
    { "id": "no_action", "type": "action", "text": "Action" },
    { "id": "end", "type": "end", "text": "End" }
  ],
  "edges": [
    { "id": "e1", "from": "start", "to": "step" },
    { "id": "e2", "from": "step", "to": "decision" },
    { "id": "e3", "from": "decision", "to": "yes_action", "label": "Yes", "type": "yes" },
    { "id": "e4", "from": "decision", "to": "no_action", "label": "No", "type": "no" },
    { "id": "e5", "from": "yes_action", "to": "end", "type": "merge" },
    { "id": "e6", "from": "no_action", "to": "end", "type": "merge" }
  ],
  "settings": {
    "direction": "TB",
    "autoLayout": true,
    "showEdgeLabels": true,
    "validateBeforeRender": true
  }
}"""

LEGACY_JSON_EXAMPLE = """{
  "title": "Simple Flowchart",
  "steps": [
    { "text": "Start", "type": "start" },
    { "text": "Prepare sample", "type": "step" },
    { "text": "Record result", "type": "action" },
    { "text": "End", "type": "end" }
  ]
}"""

TYPE_ALIASES = {
    "start": StepType.TERMINATOR,
    "end": StepType.TERMINATOR,
    "start/end": StepType.TERMINATOR,
    "start / end": StepType.TERMINATOR,
    "terminator": StepType.TERMINATOR,
    "oval": StepType.TERMINATOR,
    "step": StepType.PROCESS,
    "action": StepType.PROCESS,
    "process": StepType.PROCESS,
    "rectangle": StepType.PROCESS,
    "step/action": StepType.PROCESS,
    "step / action": StepType.PROCESS,
    "decision": StepType.DECISION,
    "diamond": StepType.DECISION,
    "input": StepType.INPUT_OUTPUT,
    "output": StepType.INPUT_OUTPUT,
    "input/output": StepType.INPUT_OUTPUT,
    "input / output": StepType.INPUT_OUTPUT,
    "input_output": StepType.INPUT_OUTPUT,
    "io": StepType.INPUT_OUTPUT,
    "parallelogram": StepType.INPUT_OUTPUT,
}

NODE_TYPE_ALIASES = {
    "start": FlowNodeType.START,
    "end": FlowNodeType.END,
    "step": FlowNodeType.PROCESS,
    "process": FlowNodeType.PROCESS,
    "action": FlowNodeType.ACTION,
    "rectangle": FlowNodeType.PROCESS,
    "decision": FlowNodeType.DECISION,
    "diamond": FlowNodeType.DECISION,
    "input": FlowNodeType.INPUT,
    "output": FlowNodeType.OUTPUT,
    "input/output": FlowNodeType.INPUT,
    "input / output": FlowNodeType.INPUT,
    "input_output": FlowNodeType.INPUT,
    "note": FlowNodeType.NOTE,
    "connector": FlowNodeType.CONNECTOR,
}

EDGE_TYPE_ALIASES = {
    "normal": EdgeKind.NORMAL,
    "yes": EdgeKind.YES,
    "no": EdgeKind.NO,
    "loop": EdgeKind.LOOP,
    "merge": EdgeKind.MERGE,
}


def parse_flowchart_json(raw_json: str) -> ParsedFlowchart:
    try:
        payload = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        raise JsonImportError(f"Please enter valid JSON. {exc.msg} at line {exc.lineno}, column {exc.colno}.") from exc

    title = "Flowchart"
    metadata: dict[str, str] = {}
    if isinstance(payload, dict):
        title_value = payload.get("title")
        if isinstance(title_value, str) and title_value.strip():
            title = title_value.strip()
        metadata = _parse_metadata(payload.get("metadata"))
        if "nodes" in payload or "edges" in payload:
            return _parse_graph_payload(payload, title, metadata)
        raw_steps = payload.get("steps")
    else:
        raw_steps = payload

    if not isinstance(raw_steps, list):
        raise JsonImportError('JSON must be an array of steps or an object with a "steps" array.')

    steps = [_parse_step(raw_step, index) for index, raw_step in enumerate(raw_steps, start=1)]
    if not steps:
        raise JsonImportError("JSON needs at least one step.")

    graph = _legacy_steps_to_graph(title, steps)
    return ParsedFlowchart(title=title, steps=steps, metadata=metadata, graph=graph, issues=[], is_graph_json=False)


def _parse_graph_payload(payload: dict[str, Any], title: str, metadata: dict[str, str]) -> ParsedFlowchart:
    if not isinstance(payload.get("version"), str) or not payload.get("version", "").strip():
        raise JsonImportError("FLOW_SCHEMA: Graph JSON must include a version string.")
    raw_nodes = payload.get("nodes")
    raw_edges = payload.get("edges")
    if not isinstance(raw_nodes, list):
        raise JsonImportError('FLOW_SCHEMA: Graph JSON must include a "nodes" array.')
    if not isinstance(raw_edges, list):
        raise JsonImportError('FLOW_SCHEMA: Graph JSON must include an "edges" array.')

    direction = _parse_direction(payload.get("settings"))
    nodes = [_parse_graph_node(raw_node, index) for index, raw_node in enumerate(raw_nodes, start=1)]
    edges = [_parse_graph_edge(raw_edge, index) for index, raw_edge in enumerate(raw_edges, start=1)]
    graph = FlowGraph(title=title, nodes=nodes, edges=edges, direction=direction)
    issues = validate_graph(graph)
    if any(issue.severity == "error" for issue in issues):
        raise JsonImportError(_format_issues(issues))
    steps = [Step(id=node.id, label=node.text, type=_node_type_to_step_type(node.type)) for node in nodes]
    return ParsedFlowchart(title=title, steps=steps, metadata=metadata, graph=graph, issues=issues, is_graph_json=True)


def _parse_metadata(raw_metadata: Any) -> dict[str, str]:
    if not isinstance(raw_metadata, dict):
        return {}
    metadata: dict[str, str] = {}
    for key in ["author", "course", "lab", "description"]:
        value = raw_metadata.get(key)
        if isinstance(value, str) and value.strip():
            metadata[key] = value.strip()
    return metadata


def _parse_graph_node(raw_node: Any, index: int) -> FlowNode:
    if not isinstance(raw_node, dict):
        raise JsonImportError(f"FLOW_SCHEMA: Node {index} must be an object.")
    node_id = _first_text(raw_node, ["id"])
    if not node_id:
        raise JsonImportError(f"FLOW_SCHEMA: Node {index} needs an id.")
    text = _first_text(raw_node, ["text", "label", "name"])
    raw_type = _first_text(raw_node, ["type", "shape", "kind"])
    if not raw_type:
        raise JsonImportError(f"FLOW_SCHEMA: Node {index} needs a type.")
    node_type = _parse_node_type(raw_type, index)
    description = _first_text(raw_node, ["description"])
    position = _parse_position(raw_node.get("position"))
    return FlowNode(id=node_id, type=node_type, text=text, description=description, position=position)


def _parse_graph_edge(raw_edge: Any, index: int) -> FlowEdge:
    if not isinstance(raw_edge, dict):
        raise JsonImportError(f"FLOW_SCHEMA: Edge {index} must be an object.")
    from_id = _first_text(raw_edge, ["from", "source"])
    to_id = _first_text(raw_edge, ["to", "target"])
    if not from_id or not to_id:
        raise JsonImportError(f"FLOW_SCHEMA: Edge {index} needs from and to node ids.")
    edge_id = _first_text(raw_edge, ["id"]) or f"edge_{index}"
    label = _first_text(raw_edge, ["label"])
    condition = _first_text(raw_edge, ["condition"])
    raw_kind = _first_text(raw_edge, ["type", "kind"]) or "normal"
    kind = _parse_edge_kind(raw_kind, index)
    return FlowEdge(id=edge_id, from_id=from_id, to_id=to_id, label=label, kind=kind, condition=condition)


def _parse_step(raw_step: Any, index: int) -> Step:
    if not isinstance(raw_step, dict):
        raise JsonImportError(f"Step {index} must be an object with text/label and type.")

    label = _first_text(raw_step, ["text", "label", "step", "name"])
    if not label:
        raise JsonImportError(f"Step {index} needs a text or label value.")

    raw_type = _first_text(raw_step, ["type", "shape", "kind"])
    if not raw_type:
        raise JsonImportError(f"Step {index} needs a type value.")

    step_type = _parse_step_type(raw_type, index)
    step_id = _first_text(raw_step, ["id"]) or _slug(label)
    return Step(id=step_id, label=label, type=step_type)


def _parse_step_type(raw_type: str, index: int) -> StepType:
    normalized = " ".join(raw_type.strip().lower().replace("-", "_").split())
    lookup_key = normalized.replace("_", "/") if normalized == "input/output" else normalized
    step_type = TYPE_ALIASES.get(lookup_key) or TYPE_ALIASES.get(normalized.replace("_", " "))
    if step_type is None:
        allowed = "start, end, step, action, decision, input/output"
        raise JsonImportError(f'Unknown type in step {index}: "{raw_type}". Allowed values: {allowed}.')
    return step_type


def _parse_node_type(raw_type: str, index: int) -> FlowNodeType:
    normalized = _normalize_type(raw_type)
    node_type = NODE_TYPE_ALIASES.get(normalized) or NODE_TYPE_ALIASES.get(normalized.replace("_", " "))
    if node_type is None:
        allowed = "start, end, process, action, decision, input, output, note, connector"
        raise JsonImportError(f'FLOW_SCHEMA: Unknown node type in node {index}: "{raw_type}". Allowed values: {allowed}.')
    return node_type


def _parse_edge_kind(raw_kind: str, index: int) -> EdgeKind:
    normalized = _normalize_type(raw_kind)
    edge_kind = EDGE_TYPE_ALIASES.get(normalized)
    if edge_kind is None:
        allowed = "normal, yes, no, loop, merge"
        raise JsonImportError(f'FLOW_SCHEMA: Unknown edge type in edge {index}: "{raw_kind}". Allowed values: {allowed}.')
    return edge_kind


def _parse_direction(settings: Any) -> FlowDirection:
    if isinstance(settings, dict):
        direction = settings.get("direction")
        if isinstance(direction, str) and direction.upper() == "TB":
            return FlowDirection.TOP_BOTTOM
    return FlowDirection.LEFT_RIGHT


def _parse_position(raw_position: Any) -> tuple[float, float] | None:
    if not isinstance(raw_position, dict):
        return None
    x = raw_position.get("x")
    y = raw_position.get("y")
    if isinstance(x, (int, float)) and isinstance(y, (int, float)):
        return float(x), float(y)
    return None


def _legacy_steps_to_graph(title: str, steps: list[Step]) -> FlowGraph:
    nodes = [
        FlowNode(id=step.id or f"node_{index}", type=_step_type_to_node_type(step), text=step.label)
        for index, step in enumerate(steps, start=1)
    ]
    edges = [
        FlowEdge(id=f"edge_{index}", from_id=nodes[index - 1].id, to_id=nodes[index].id)
        for index in range(1, len(nodes))
    ]
    return FlowGraph(title=title, nodes=nodes, edges=edges)


def _step_type_to_node_type(step: Step) -> FlowNodeType:
    if step.type == StepType.TERMINATOR:
        if step.label.strip().lower() == "start":
            return FlowNodeType.START
        if step.label.strip().lower() == "end":
            return FlowNodeType.END
        return FlowNodeType.PROCESS
    if step.type == StepType.DECISION:
        return FlowNodeType.DECISION
    if step.type == StepType.INPUT_OUTPUT:
        return FlowNodeType.INPUT
    return FlowNodeType.PROCESS


def _node_type_to_step_type(node_type: FlowNodeType) -> StepType:
    if node_type in {FlowNodeType.START, FlowNodeType.END}:
        return StepType.TERMINATOR
    if node_type == FlowNodeType.DECISION:
        return StepType.DECISION
    if node_type in {FlowNodeType.INPUT, FlowNodeType.OUTPUT}:
        return StepType.INPUT_OUTPUT
    return StepType.PROCESS


def _format_issues(issues: list[ValidationIssue]) -> str:
    return "\n".join(
        f"{issue.code} [{issue.severity}]: {issue.message}"
        for issue in issues
        if issue.severity == "error"
    )


def _normalize_type(raw_type: str) -> str:
    return " ".join(raw_type.strip().lower().replace("-", "_").split())


def _first_text(raw_step: dict[str, Any], keys: list[str]) -> str:
    for key in keys:
        value = raw_step.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _slug(text: str) -> str:
    slug = "".join(char.lower() if char.isalnum() else "-" for char in text).strip("-")
    return slug or "step"
