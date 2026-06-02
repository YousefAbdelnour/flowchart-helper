from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from math import ceil


class StepType(StrEnum):
    TERMINATOR = "terminator"
    PROCESS = "process"
    DECISION = "decision"
    INPUT_OUTPUT = "input_output"


class FlowDirection(StrEnum):
    LEFT_RIGHT = "LR"
    TOP_BOTTOM = "TB"


class FlowNodeType(StrEnum):
    START = "start"
    END = "end"
    PROCESS = "process"
    ACTION = "action"
    DECISION = "decision"
    INPUT = "input"
    OUTPUT = "output"
    NOTE = "note"
    CONNECTOR = "connector"


class EdgeKind(StrEnum):
    NORMAL = "normal"
    YES = "yes"
    NO = "no"
    LOOP = "loop"
    MERGE = "merge"


@dataclass(frozen=True)
class ShapeDefinition:
    name: str
    shape: str
    fill: str
    outline: str
    text: str


@dataclass(frozen=True)
class Step:
    id: str
    label: str
    type: StepType


@dataclass(frozen=True)
class FlowNode:
    id: str
    type: FlowNodeType
    text: str
    description: str = ""
    position: tuple[float, float] | None = None


@dataclass(frozen=True)
class FlowEdge:
    id: str
    from_id: str
    to_id: str
    label: str = ""
    kind: EdgeKind = EdgeKind.NORMAL
    condition: str = ""


@dataclass(frozen=True)
class FlowGraph:
    title: str
    nodes: list[FlowNode]
    edges: list[FlowEdge]
    direction: FlowDirection = FlowDirection.LEFT_RIGHT


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    severity: str
    message: str
    node_id: str = ""
    edge_id: str = ""


@dataclass(frozen=True)
class BranchSplit:
    yes: list[Step]
    no: list[Step]
    tail: list[Step]


@dataclass(frozen=True)
class NodeLayout:
    id: str
    label: str
    type: StepType
    shape: str
    x: float
    y: float
    width: float
    height: float
    lane: str
    page_index: int = 0

    @property
    def left(self) -> float:
        return self.x - self.width / 2

    @property
    def right(self) -> float:
        return self.x + self.width / 2

    @property
    def top(self) -> float:
        return self.y - self.height / 2

    @property
    def bottom(self) -> float:
        return self.y + self.height / 2


@dataclass(frozen=True)
class EdgeLayout:
    from_id: str
    to_id: str
    label: str = ""
    kind: EdgeKind = EdgeKind.NORMAL


@dataclass(frozen=True)
class FlowLayout:
    nodes: list[NodeLayout]
    edges: list[EdgeLayout]
    width: float
    height: float
    direction: FlowDirection = FlowDirection.LEFT_RIGHT
    paper_width: float = 0.0
    paper_height: float = 0.0
    page_count: int = 0
    page_gap: float = 0.0


SHAPE_DEFINITIONS: dict[StepType, ShapeDefinition] = {
    StepType.TERMINATOR: ShapeDefinition(
        name="Start / End",
        shape="oval",
        fill="#aed5ec",
        outline="#8dbed9",
        text="#263943",
    ),
    StepType.PROCESS: ShapeDefinition(
        name="Step / Action",
        shape="rectangle",
        fill="#cfe8ec",
        outline="#aed4da",
        text="#263943",
    ),
    StepType.DECISION: ShapeDefinition(
        name="Decision",
        shape="diamond",
        fill="#fed783",
        outline="#efbd54",
        text="#453417",
    ),
    StepType.INPUT_OUTPUT: ShapeDefinition(
        name="Input / Output",
        shape="parallelogram",
        fill="#d8e7ff",
        outline="#aac2ed",
        text="#263943",
    ),
}

NODE_WIDTH = 154
NODE_HEIGHT = 76
NODE_TEXT_MAX_CHARS = 18
NODE_TEXT_LINE_HEIGHT = 16
NODE_VERTICAL_PADDING = 28
HORIZONTAL_GAP = 230
MARGIN_X = 100
MAIN_Y = 300
BRANCH_OFFSET_Y = 132
CANVAS_PADDING = 90
GRAPH_LEVEL_GAP = 175
GRAPH_LANE_GAP = 170
A4_PAGE_WIDTH = 595.0
A4_PAGE_HEIGHT = 842.0
A4_PAGE_GAP = 56.0
A4_MARGIN_X = 36.0
A4_MARGIN_TOP = 84.0
A4_MARGIN_BOTTOM = 54.0
A4_COLUMN_COUNT = 3
A4_ROW_GAP = 38.0
A4_GROUP_GAP = 34.0
LOOP_ROUTE_OFFSET = 56.0
LOOP_ROUTE_PAGE_PADDING = A4_MARGIN_X


def route_loop_edge(
    start_node: NodeLayout,
    end_node: NodeLayout,
    layout: FlowLayout | None = None,
) -> list[tuple[float, float]]:
    if abs(end_node.y - start_node.y) >= abs(end_node.x - start_node.x):
        offset_x = min(start_node.left, end_node.left) - LOOP_ROUTE_OFFSET
        page_bounds = _same_page_bounds(start_node, end_node, layout)
        if page_bounds:
            page_left, _page_top, page_right, _page_bottom = page_bounds
            offset_x = _clamp(offset_x, page_left + LOOP_ROUTE_PAGE_PADDING, page_right - LOOP_ROUTE_PAGE_PADDING)
        return [
            (start_node.left, start_node.y),
            (offset_x, start_node.y),
            (offset_x, end_node.y),
            (end_node.left, end_node.y),
        ]

    offset_y = min(start_node.top, end_node.top) - LOOP_ROUTE_OFFSET
    page_bounds = _same_page_bounds(start_node, end_node, layout)
    if page_bounds:
        _page_left, page_top, _page_right, page_bottom = page_bounds
        offset_y = _clamp(offset_y, page_top + LOOP_ROUTE_PAGE_PADDING, page_bottom - LOOP_ROUTE_PAGE_PADDING)
    return [
        (start_node.x, start_node.top),
        (start_node.x, offset_y),
        (end_node.x, offset_y),
        (end_node.x, end_node.top),
    ]


def _same_page_bounds(
    start_node: NodeLayout,
    end_node: NodeLayout,
    layout: FlowLayout | None,
) -> tuple[float, float, float, float] | None:
    if not layout or not layout.paper_width or not layout.paper_height:
        return None
    if start_node.page_index != end_node.page_index:
        return None
    page_left = start_node.page_index * (layout.paper_width + layout.page_gap)
    return page_left, 0.0, page_left + layout.paper_width, layout.paper_height


def _clamp(value: float, minimum: float, maximum: float) -> float:
    if minimum > maximum:
        return value
    return max(minimum, min(maximum, value))


def sample_steps() -> list[Step]:
    return [
        Step(id="start", label="Start", type=StepType.TERMINATOR),
        Step(id="step", label="Step", type=StepType.PROCESS),
        Step(id="decision", label="Decision", type=StepType.DECISION),
        Step(id="yes-action", label="Action", type=StepType.PROCESS),
        Step(id="yes-end", label="End", type=StepType.TERMINATOR),
        Step(id="no-action", label="Action", type=StepType.PROCESS),
        Step(id="no-end", label="End", type=StepType.TERMINATOR),
    ]


def wrap_node_text(text: str, max_chars: int = NODE_TEXT_MAX_CHARS) -> list[str]:
    words = text.split()
    if not words:
        return [""]
    lines: list[str] = []
    current = ""
    for word in words:
        pieces = _split_long_word(word, max_chars)
        for piece in pieces:
            if not current:
                current = piece
            elif len(current) + 1 + len(piece) <= max_chars:
                current = f"{current} {piece}"
            else:
                lines.append(current)
                current = piece
    if current:
        lines.append(current)
    return lines


def normalize_steps(steps: list[Step]) -> list[Step]:
    normalized: list[Step] = []
    used_ids: set[str] = set()

    for index, step in enumerate(steps, start=1):
        label = step.label.strip()
        if not label:
            continue
        step_id = _unique_step_id(step.id or f"step-{index}", used_ids)
        normalized.append(Step(id=step_id, label=label, type=step.type))

    return normalized


def split_decision_branches(steps_after_decision: list[Step]) -> BranchSplit:
    if not steps_after_decision:
        return BranchSplit(yes=[], no=[], tail=[])

    first_end = _find_first_terminator_index(steps_after_decision)
    if first_end is not None:
        yes = steps_after_decision[: first_end + 1]
        remaining = steps_after_decision[first_end + 1 :]
        second_end = _find_first_terminator_index(remaining)
        if second_end is not None:
            no = remaining[: second_end + 1]
            tail = remaining[second_end + 1 :]
            return BranchSplit(yes=yes, no=no, tail=tail)

    midpoint = ceil(len(steps_after_decision) / 2)
    return BranchSplit(
        yes=steps_after_decision[:midpoint],
        no=steps_after_decision[midpoint:],
        tail=[],
    )


def build_flow_layout(steps: list[Step], direction: FlowDirection = FlowDirection.LEFT_RIGHT) -> FlowLayout:
    clean_steps = normalize_steps(steps)
    if not clean_steps:
        return FlowLayout(nodes=[], edges=[], width=900, height=560, direction=direction)

    decision_index = next(
        (index for index, step in enumerate(clean_steps) if step.type == StepType.DECISION),
        None,
    )
    if decision_index is None:
        return _orient_layout(_build_linear_layout(clean_steps), direction)

    prefix = clean_steps[: decision_index + 1]
    decision = clean_steps[decision_index]
    branches = split_decision_branches(clean_steps[decision_index + 1 :])

    nodes: list[NodeLayout] = []
    edges: list[EdgeLayout] = []

    for index, step in enumerate(prefix):
        nodes.append(_node_for_step(step, x=MARGIN_X + index * HORIZONTAL_GAP, y=MAIN_Y, lane="main"))
        if index > 0:
            edges.append(EdgeLayout(from_id=prefix[index - 1].id, to_id=step.id))

    decision_x = MARGIN_X + decision_index * HORIZONTAL_GAP
    branch_start_x = decision_x + HORIZONTAL_GAP
    yes_nodes = _branch_nodes(branches.yes, branch_start_x, MAIN_Y - BRANCH_OFFSET_Y, "yes")
    no_nodes = _branch_nodes(branches.no, branch_start_x, MAIN_Y + BRANCH_OFFSET_Y, "no")
    nodes.extend(yes_nodes)
    nodes.extend(no_nodes)

    if yes_nodes:
        edges.append(EdgeLayout(from_id=decision.id, to_id=yes_nodes[0].id, label="Yes"))
        edges.extend(_sequence_edges(yes_nodes))
    if no_nodes:
        edges.append(EdgeLayout(from_id=decision.id, to_id=no_nodes[0].id, label="No"))
        edges.extend(_sequence_edges(no_nodes))

    branch_end_x = max(
        [decision_x, *(node.x for node in yes_nodes), *(node.x for node in no_nodes)]
    )
    tail_start_x = branch_end_x + HORIZONTAL_GAP
    tail_nodes = _branch_nodes(branches.tail, tail_start_x, MAIN_Y, "main")
    nodes.extend(tail_nodes)
    if tail_nodes:
        if yes_nodes:
            edges.append(EdgeLayout(from_id=yes_nodes[-1].id, to_id=tail_nodes[0].id))
        if no_nodes:
            edges.append(EdgeLayout(from_id=no_nodes[-1].id, to_id=tail_nodes[0].id))
        if not yes_nodes and not no_nodes:
            edges.append(EdgeLayout(from_id=decision.id, to_id=tail_nodes[0].id))
        edges.extend(_sequence_edges(tail_nodes))

    return _orient_layout(_layout_with_bounds(nodes, edges), direction)


def build_a4_paper_flow_layout(steps: list[Step]) -> FlowLayout:
    clean_steps = normalize_steps(steps)
    if not clean_steps:
        return FlowLayout(
            nodes=[],
            edges=[],
            width=A4_PAGE_WIDTH,
            height=A4_PAGE_HEIGHT,
            direction=FlowDirection.TOP_BOTTOM,
            paper_width=A4_PAGE_WIDTH,
            paper_height=A4_PAGE_HEIGHT,
            page_count=1,
            page_gap=A4_PAGE_GAP,
        )

    nodes: list[NodeLayout] = []
    page_index = 0
    column_index = 0
    cursor = _a4_column_start(column_index)

    for step in clean_steps:
        width, height = _node_size_for_text(step.label, step.type)
        if not _a4_fits(cursor, height, column_index):
            page_index, column_index, cursor = _next_a4_column(page_index, column_index)
        if not _a4_fits(cursor, height, column_index):
            page_index, column_index, cursor = page_index + 1, 0, _a4_column_start(0)

        x = _a4_page_left(page_index) + _a4_column_center(column_index)
        y = _a4_node_center_y(cursor, height, column_index)
        node = _node_for_step(step, x=x, y=y, lane=f"page-{page_index + 1}-column-{column_index + 1}")
        nodes.append(
            NodeLayout(
                id=node.id,
                label=node.label,
                type=node.type,
                shape=node.shape,
                x=node.x,
                y=node.y,
                width=node.width,
                height=node.height,
                lane=node.lane,
                page_index=page_index,
            )
        )
        cursor = _a4_next_cursor(cursor, height, column_index)

    page_count = max(node.page_index for node in nodes) + 1
    return FlowLayout(
        nodes=nodes,
        edges=_sequence_edges(nodes),
        width=page_count * A4_PAGE_WIDTH + (page_count - 1) * A4_PAGE_GAP,
        height=A4_PAGE_HEIGHT,
        direction=FlowDirection.TOP_BOTTOM,
        paper_width=A4_PAGE_WIDTH,
        paper_height=A4_PAGE_HEIGHT,
        page_count=page_count,
        page_gap=A4_PAGE_GAP,
    )


def build_a4_paper_graph_layout(graph: FlowGraph) -> FlowLayout:
    if not graph.nodes:
        return FlowLayout(
            nodes=[],
            edges=[],
            width=A4_PAGE_WIDTH,
            height=A4_PAGE_HEIGHT,
            direction=FlowDirection.TOP_BOTTOM,
            paper_width=A4_PAGE_WIDTH,
            paper_height=A4_PAGE_HEIGHT,
            page_count=1,
            page_gap=A4_PAGE_GAP,
        )

    ranks = _graph_ranks(graph)
    rank_groups: dict[int, list[FlowNode]] = {}
    for node in graph.nodes:
        rank_groups.setdefault(ranks.get(node.id, 0), []).append(node)

    nodes: list[NodeLayout] = []
    page_index = 0
    column_index = 0
    cursor = _a4_column_start(column_index)

    for rank in sorted(rank_groups):
        group = rank_groups[rank]
        group_layouts = [_node_for_graph_node(node, x=0, y=0, lane=f"rank-{rank}") for node in group]
        group_height = max(node.height for node in group_layouts)
        if not _a4_fits(cursor, group_height, column_index):
            page_index, column_index, cursor = _next_a4_column(page_index, column_index)
        if not _a4_fits(cursor, group_height, column_index):
            page_index, column_index, cursor = page_index + 1, 0, _a4_column_start(0)

        group_nodes = _position_a4_rank_group(group_layouts, page_index, column_index, cursor)
        nodes.extend(group_nodes)
        cursor = _a4_next_cursor(cursor, group_height, column_index)

    page_count = max(node.page_index for node in nodes) + 1
    edges = [
        EdgeLayout(from_id=edge.from_id, to_id=edge.to_id, label=edge.label, kind=edge.kind)
        for edge in graph.edges
    ]
    return FlowLayout(
        nodes=nodes,
        edges=edges,
        width=page_count * A4_PAGE_WIDTH + (page_count - 1) * A4_PAGE_GAP,
        height=A4_PAGE_HEIGHT,
        direction=FlowDirection.TOP_BOTTOM,
        paper_width=A4_PAGE_WIDTH,
        paper_height=A4_PAGE_HEIGHT,
        page_count=page_count,
        page_gap=A4_PAGE_GAP,
    )


def validate_graph(graph: FlowGraph) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    nodes_by_id: dict[str, FlowNode] = {}
    incoming: dict[str, list[FlowEdge]] = {}
    outgoing: dict[str, list[FlowEdge]] = {}

    for node in graph.nodes:
        if node.id in nodes_by_id:
            issues.append(_issue("FLOW_003", "error", f'Duplicate node id "{node.id}".', node_id=node.id))
        nodes_by_id[node.id] = node
        incoming.setdefault(node.id, [])
        outgoing.setdefault(node.id, [])
        if not node.text.strip():
            issues.append(_issue("FLOW_013", "error", f'Node "{node.id}" needs text.', node_id=node.id))
        if len(node.text) > 90:
            issues.append(
                _issue("FLOW_014", "warning", f'Node "{node.text}" is long; consider making it more concise.', node_id=node.id)
            )
        if node.type == FlowNodeType.DECISION and not node.text.strip().endswith("?"):
            issues.append(
                _issue("FLOW_015", "warning", f'Decision node "{node.text}" should be written as a question.', node_id=node.id)
            )

    for edge in graph.edges:
        if edge.from_id not in nodes_by_id or edge.to_id not in nodes_by_id:
            issues.append(
                _issue(
                    "FLOW_004",
                    "error",
                    f'Edge "{edge.id}" references missing node id(s): {edge.from_id} -> {edge.to_id}.',
                    edge_id=edge.id,
                )
            )
            continue
        outgoing.setdefault(edge.from_id, []).append(edge)
        incoming.setdefault(edge.to_id, []).append(edge)
    starts = [node for node in graph.nodes if node.type == FlowNodeType.START]
    ends = [node for node in graph.nodes if node.type == FlowNodeType.END]
    if len(starts) != 1:
        issues.append(_issue("FLOW_001", "error", "Flowchart must have exactly one start node."))
    if not ends:
        issues.append(_issue("FLOW_002", "error", "Flowchart must have at least one end node."))

    for start in starts:
        if incoming.get(start.id):
            issues.append(_issue("FLOW_005", "error", "Start node cannot have incoming edges.", node_id=start.id))
    for end in ends:
        if outgoing.get(end.id):
            issues.append(_issue("FLOW_006", "error", "End node cannot have outgoing edges.", node_id=end.id))

    for node in graph.nodes:
        node_outgoing = outgoing.get(node.id, [])
        if node.type == FlowNodeType.DECISION:
            if len(node_outgoing) < 2:
                issues.append(
                    _issue(
                        "FLOW_007",
                        "error",
                        f'Decision node "{node.text}" must have at least two outgoing branches.',
                        node_id=node.id,
                    )
                )
            if any(not edge.label.strip() for edge in node_outgoing):
                issues.append(
                    _issue(
                        "FLOW_008",
                        "warning",
                        f'Decision node "{node.text}" should label each outgoing branch.',
                        node_id=node.id,
                    )
                )
            issues.extend(_yes_no_sequence_warnings(node, node_outgoing, outgoing, nodes_by_id))

    if len(starts) == 1:
        reachable = _reachable_from(starts[0].id, outgoing)
        for node in graph.nodes:
            if node.id not in reachable:
                issues.append(
                    _issue("FLOW_010", "error", f'Node "{node.text}" is not reachable from the start node.', node_id=node.id)
                )
        for node in graph.nodes:
            if node.type != FlowNodeType.END and node.id in reachable and not outgoing.get(node.id):
                issues.append(
                    _issue("FLOW_011", "error", f'Node "{node.text}" dead-ends before an end node.', node_id=node.id)
                )

    return issues


def build_graph_layout(graph: FlowGraph) -> FlowLayout:
    if not graph.nodes:
        return FlowLayout(nodes=[], edges=[], width=900, height=560, direction=graph.direction)

    ranks = _graph_ranks(graph)
    rank_groups: dict[int, list[FlowNode]] = {}
    for node in graph.nodes:
        rank_groups.setdefault(ranks.get(node.id, 0), []).append(node)

    nodes: list[NodeLayout] = []
    for rank in sorted(rank_groups):
        group = rank_groups[rank]
        lane_start = -((len(group) - 1) * GRAPH_LANE_GAP) / 2
        for lane_index, node in enumerate(group):
            x = MARGIN_X + rank * GRAPH_LEVEL_GAP
            y = MAIN_Y + lane_start + lane_index * GRAPH_LANE_GAP
            if node.position is not None:
                x, y = node.position
            nodes.append(_node_for_graph_node(node, x=x, y=y, lane=f"rank-{rank}"))

    edges = [
        EdgeLayout(from_id=edge.from_id, to_id=edge.to_id, label=edge.label, kind=edge.kind)
        for edge in graph.edges
    ]
    return _orient_layout(_layout_with_bounds(nodes, edges), graph.direction)


def _build_linear_layout(steps: list[Step]) -> FlowLayout:
    nodes = [
        _node_for_step(step, x=MARGIN_X + index * HORIZONTAL_GAP, y=MAIN_Y, lane="main")
        for index, step in enumerate(steps)
    ]
    return _layout_with_bounds(nodes, _sequence_edges(nodes))


def _a4_page_left(page_index: int) -> float:
    return page_index * (A4_PAGE_WIDTH + A4_PAGE_GAP)


def _a4_column_center(column_index: int) -> float:
    content_width = A4_PAGE_WIDTH - A4_MARGIN_X * 2
    column_width = content_width / A4_COLUMN_COUNT
    return A4_MARGIN_X + column_width * column_index + column_width / 2


def _a4_column_start(column_index: int) -> float:
    if _a4_column_flows_down(column_index):
        return A4_MARGIN_TOP
    return A4_PAGE_HEIGHT - A4_MARGIN_BOTTOM


def _a4_node_center_y(cursor: float, node_height: float, column_index: int) -> float:
    if _a4_column_flows_down(column_index):
        return cursor + node_height / 2
    return cursor - node_height / 2


def _a4_next_cursor(cursor: float, node_height: float, column_index: int) -> float:
    if _a4_column_flows_down(column_index):
        return cursor + node_height + A4_ROW_GAP
    return cursor - node_height - A4_ROW_GAP


def _a4_fits(cursor: float, node_height: float, column_index: int) -> bool:
    if _a4_column_flows_down(column_index):
        return cursor + node_height <= A4_PAGE_HEIGHT - A4_MARGIN_BOTTOM
    return cursor - node_height >= A4_MARGIN_TOP


def _a4_column_flows_down(column_index: int) -> bool:
    return column_index % 2 == 0


def _next_a4_column(page_index: int, column_index: int) -> tuple[int, int, float]:
    if column_index < A4_COLUMN_COUNT - 1:
        next_column = column_index + 1
        return page_index, next_column, _a4_column_start(next_column)
    return page_index + 1, 0, _a4_column_start(0)


def _position_a4_rank_group(
    group_layouts: list[NodeLayout],
    page_index: int,
    column_index: int,
    cursor: float,
) -> list[NodeLayout]:
    if len(group_layouts) == 1:
        node = group_layouts[0]
        return [
            _copy_node_position(
                node,
                x=_a4_page_left(page_index) + _a4_column_center(column_index),
                y=_a4_node_center_y(cursor, node.height, column_index),
                page_index=page_index,
            )
        ]

    group_width = sum(node.width for node in group_layouts) + (len(group_layouts) - 1) * A4_GROUP_GAP
    start_x = _a4_page_left(page_index) + (A4_PAGE_WIDTH - group_width) / 2
    y = _a4_node_center_y(cursor, max(node.height for node in group_layouts), column_index)
    positioned: list[NodeLayout] = []
    current_x = start_x
    for node in group_layouts:
        positioned.append(
            _copy_node_position(node, x=current_x + node.width / 2, y=y, page_index=page_index)
        )
        current_x += node.width + A4_GROUP_GAP
    return positioned


def _copy_node_position(node: NodeLayout, x: float, y: float, page_index: int) -> NodeLayout:
    return NodeLayout(
        id=node.id,
        label=node.label,
        type=node.type,
        shape=node.shape,
        x=x,
        y=y,
        width=node.width,
        height=node.height,
        lane=node.lane,
        page_index=page_index,
    )


def _branch_nodes(steps: list[Step], start_x: float, y: float, lane: str) -> list[NodeLayout]:
    return [
        _node_for_step(step, x=start_x + index * HORIZONTAL_GAP, y=y, lane=lane)
        for index, step in enumerate(steps)
    ]


def _node_for_step(step: Step, x: float, y: float, lane: str) -> NodeLayout:
    definition = SHAPE_DEFINITIONS[step.type]
    width, height = _node_size_for_text(step.label, step.type)
    return NodeLayout(
        id=step.id,
        label=step.label,
        type=step.type,
        shape=definition.shape,
        x=x,
        y=y,
        width=width,
        height=height,
        lane=lane,
    )


def _sequence_edges(nodes: list[NodeLayout]) -> list[EdgeLayout]:
    return [
        EdgeLayout(from_id=nodes[index - 1].id, to_id=nodes[index].id)
        for index in range(1, len(nodes))
    ]


def _layout_with_bounds(nodes: list[NodeLayout], edges: list[EdgeLayout]) -> FlowLayout:
    max_right = max(node.right for node in nodes) if nodes else 800
    max_bottom = max(node.bottom for node in nodes) if nodes else 480
    min_top = min(node.top for node in nodes) if nodes else 0
    height = max(560, max_bottom - min_top + CANVAS_PADDING * 2)
    width = max(900, max_right + CANVAS_PADDING)
    return FlowLayout(nodes=nodes, edges=edges, width=width, height=height)


def _node_for_graph_node(node: FlowNode, x: float, y: float, lane: str) -> NodeLayout:
    render_type = _render_step_type(node.type)
    definition = SHAPE_DEFINITIONS[render_type]
    width, height = _node_size_for_text(node.text, render_type)
    return NodeLayout(
        id=node.id,
        label=node.text,
        type=render_type,
        shape=definition.shape,
        x=x,
        y=y,
        width=width,
        height=height,
        lane=lane,
    )


def _node_size_for_text(text: str, step_type: StepType) -> tuple[float, float]:
    lines = wrap_node_text(text)
    width = NODE_WIDTH
    min_height = NODE_HEIGHT
    if step_type == StepType.DECISION:
        min_height = 96
    needed_height = len(lines) * NODE_TEXT_LINE_HEIGHT + NODE_VERTICAL_PADDING
    return width, max(min_height, needed_height)


def _split_long_word(word: str, max_chars: int) -> list[str]:
    if len(word) <= max_chars:
        return [word]
    return [word[index : index + max_chars] for index in range(0, len(word), max_chars)]


def _render_step_type(node_type: FlowNodeType) -> StepType:
    if node_type in {FlowNodeType.START, FlowNodeType.END}:
        return StepType.TERMINATOR
    if node_type == FlowNodeType.DECISION:
        return StepType.DECISION
    if node_type in {FlowNodeType.INPUT, FlowNodeType.OUTPUT}:
        return StepType.INPUT_OUTPUT
    return StepType.PROCESS


def _orient_layout(layout: FlowLayout, direction: FlowDirection) -> FlowLayout:
    if direction == FlowDirection.LEFT_RIGHT:
        return FlowLayout(nodes=layout.nodes, edges=layout.edges, width=layout.width, height=layout.height, direction=direction)

    if not layout.nodes:
        return FlowLayout(nodes=[], edges=layout.edges, width=layout.width, height=layout.height, direction=direction)

    min_y = min(node.top for node in layout.nodes)
    oriented_nodes = [
        NodeLayout(
            id=node.id,
            label=node.label,
            type=node.type,
            shape=node.shape,
            x=node.y - min_y + MARGIN_X,
            y=node.x + CANVAS_PADDING,
            width=node.width,
            height=node.height,
            lane=node.lane,
        )
        for node in layout.nodes
    ]
    oriented = _layout_with_bounds(oriented_nodes, layout.edges)
    return FlowLayout(
        nodes=oriented.nodes,
        edges=oriented.edges,
        width=oriented.width,
        height=oriented.height,
        direction=direction,
    )


def _graph_ranks(graph: FlowGraph) -> dict[str, int]:
    ranks = {node.id: 0 for node in graph.nodes}
    non_loop_edges = [edge for edge in graph.edges if edge.kind != EdgeKind.LOOP]
    for _ in range(max(1, len(graph.nodes))):
        changed = False
        for edge in non_loop_edges:
            next_rank = ranks.get(edge.from_id, 0) + 1
            if next_rank > ranks.get(edge.to_id, 0):
                ranks[edge.to_id] = next_rank
                changed = True
        if not changed:
            break
    return ranks


def _issue(code: str, severity: str, message: str, node_id: str = "", edge_id: str = "") -> ValidationIssue:
    return ValidationIssue(code=code, severity=severity, message=message, node_id=node_id, edge_id=edge_id)


def _reachable_from(start_id: str, outgoing: dict[str, list[FlowEdge]]) -> set[str]:
    visited: set[str] = set()
    stack = [start_id]
    while stack:
        node_id = stack.pop()
        if node_id in visited:
            continue
        visited.add(node_id)
        stack.extend(edge.to_id for edge in outgoing.get(node_id, []))
    return visited


def _yes_no_sequence_warnings(
    decision: FlowNode,
    decision_edges: list[FlowEdge],
    outgoing: dict[str, list[FlowEdge]],
    nodes_by_id: dict[str, FlowNode],
) -> list[ValidationIssue]:
    yes_targets = {edge.to_id for edge in decision_edges if edge.kind == EdgeKind.YES or edge.label.lower() == "yes"}
    no_targets = {edge.to_id for edge in decision_edges if edge.kind == EdgeKind.NO or edge.label.lower() == "no"}
    warnings: list[ValidationIssue] = []
    for yes_target in yes_targets:
        reachable_from_yes = _reachable_from_without_loops(yes_target, outgoing)
        if no_targets & reachable_from_yes:
            warnings.append(
                _issue(
                    "FLOW_009",
                    "warning",
                    "The Yes branch points directly into the No branch. This may make the flowchart logically incorrect.",
                    node_id=decision.id,
                )
            )
            break
    return warnings


def _reachable_from_without_loops(start_id: str, outgoing: dict[str, list[FlowEdge]]) -> set[str]:
    visited: set[str] = set()
    stack = [start_id]
    while stack:
        node_id = stack.pop()
        if node_id in visited:
            continue
        visited.add(node_id)
        stack.extend(edge.to_id for edge in outgoing.get(node_id, []) if edge.kind != EdgeKind.LOOP)
    return visited


def _find_first_terminator_index(steps: list[Step]) -> int | None:
    for index, step in enumerate(steps):
        if step.type == StepType.TERMINATOR:
            return index
    return None


def _unique_step_id(candidate: str, used_ids: set[str]) -> str:
    base = "".join(char.lower() if char.isalnum() else "-" for char in candidate).strip("-")
    if not base:
        base = "step"
    step_id = base
    suffix = 2
    while step_id in used_ids:
        step_id = f"{base}-{suffix}"
        suffix += 1
    used_ids.add(step_id)
    return step_id
