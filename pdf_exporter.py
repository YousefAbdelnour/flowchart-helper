from __future__ import annotations

from dataclasses import dataclass
from math import atan2, cos, pi, sin
from pathlib import Path

from flowchart_model import EdgeKind, FlowLayout, NodeLayout, SHAPE_DEFINITIONS, wrap_node_text


A4_PORTRAIT = (595.0, 842.0)
A4_LANDSCAPE = (842.0, 595.0)
PAGE_MARGIN_X = 36.0
PAGE_TOP_MARGIN = 58.0
PAGE_BOTTOM_MARGIN = 42.0
PRINT_TARGET_SCALE = 0.85
MIN_READABLE_SCALE = 0.72
VIEWPORT_OVERLAP = 80.0
CHART_PADDING = 28.0
LOOP_OFFSET = 56.0


@dataclass(frozen=True)
class ChartBounds:
    left: float
    top: float
    right: float
    bottom: float

    @property
    def width(self) -> float:
        return self.right - self.left

    @property
    def height(self) -> float:
        return self.bottom - self.top


@dataclass(frozen=True)
class PrintViewport:
    left: float
    top: float
    right: float
    bottom: float

    @property
    def width(self) -> float:
        return self.right - self.left

    @property
    def height(self) -> float:
        return self.bottom - self.top


@dataclass(frozen=True)
class PrintPlan:
    title: str
    subtitle: str
    page_width: float
    page_height: float
    content_left: float
    content_top: float
    content_width: float
    content_height: float
    clip_bottom: float
    scale: float
    viewports: list[PrintViewport]


@dataclass(frozen=True)
class PdfTransform:
    viewport: PrintViewport
    content_left: float
    content_top: float
    scale: float

    def point(self, x: float, y: float) -> tuple[float, float]:
        return (
            self.content_left + (x - self.viewport.left) * self.scale,
            self.content_top - (y - self.viewport.top) * self.scale,
        )

    def length(self, value: float) -> float:
        return value * self.scale


def export_flowchart_pdf(path: str | Path, layout: FlowLayout, title: str = "Flowchart", subtitle: str = "") -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)

    plan = create_print_plan(layout, title, subtitle=subtitle)
    page_contents = [
        _page_commands(layout, plan, viewport, page_number, len(plan.viewports))
        for page_number, viewport in enumerate(plan.viewports, start=1)
    ]
    objects = _pdf_objects(plan.page_width, plan.page_height, page_contents)
    _write_pdf(target, objects)
    return target


def create_print_plan(layout: FlowLayout, title: str = "Flowchart", subtitle: str = "") -> PrintPlan:
    if layout.paper_width and layout.paper_height and layout.page_count:
        return PrintPlan(
            title=title,
            subtitle=subtitle,
            page_width=layout.paper_width,
            page_height=layout.paper_height,
            content_left=0.0,
            content_top=layout.paper_height,
            content_width=layout.paper_width,
            content_height=layout.paper_height,
            clip_bottom=0.0,
            scale=1.0,
            viewports=[
                PrintViewport(
                    left=page_index * (layout.paper_width + layout.page_gap),
                    top=0.0,
                    right=page_index * (layout.paper_width + layout.page_gap) + layout.paper_width,
                    bottom=layout.paper_height,
                )
                for page_index in range(layout.page_count)
            ],
        )

    page_width, page_height = _paper_size_for_layout(layout)
    content_left = PAGE_MARGIN_X
    content_top = page_height - PAGE_TOP_MARGIN
    content_width = page_width - PAGE_MARGIN_X * 2
    content_height = content_top - PAGE_BOTTOM_MARGIN

    bounds = _chart_bounds(layout)
    if bounds.width <= 0 or bounds.height <= 0:
        viewport = PrintViewport(0.0, 0.0, content_width, content_height)
        return PrintPlan(
            title=title,
            subtitle=subtitle,
            page_width=page_width,
            page_height=page_height,
            content_left=content_left,
            content_top=content_top,
            content_width=content_width,
            content_height=content_height,
            clip_bottom=PAGE_BOTTOM_MARGIN,
            scale=1.0,
            viewports=[viewport],
        )

    fit_whole_scale = min(1.0, content_width / bounds.width, content_height / bounds.height)
    if fit_whole_scale >= MIN_READABLE_SCALE:
        scale = fit_whole_scale
    else:
        cross_size = bounds.height if layout.direction.value == "LR" else bounds.width
        content_cross = content_height if layout.direction.value == "LR" else content_width
        cross_fit_scale = content_cross / cross_size if cross_size else 1.0
        scale = min(PRINT_TARGET_SCALE, max(MIN_READABLE_SCALE, cross_fit_scale))

    viewport_width = content_width / scale
    viewport_height = content_height / scale
    viewports = _tile_viewports(bounds, viewport_width, viewport_height)
    return PrintPlan(
        title=title,
        subtitle=subtitle,
        page_width=page_width,
        page_height=page_height,
        content_left=content_left,
        content_top=content_top,
        content_width=content_width,
        content_height=content_height,
        clip_bottom=PAGE_BOTTOM_MARGIN,
        scale=scale,
        viewports=viewports,
    )


def edge_label_anchor(
    start_x: float,
    start_y: float,
    end_x: float,
    end_y: float,
    label: str,
    font_size: float,
) -> tuple[float, float]:
    mid_x = start_x + (end_x - start_x) * 0.55
    mid_y = start_y + (end_y - start_y) * 0.55
    label_width = _text_width(label, font_size)
    dx = end_x - start_x
    dy = end_y - start_y
    if abs(dx) >= abs(dy):
        return mid_x - label_width / 2, mid_y + font_size * 0.8
    return mid_x + 12.0, mid_y - font_size / 3


def _page_commands(
    layout: FlowLayout,
    plan: PrintPlan,
    viewport: PrintViewport,
    page_number: int,
    page_count: int,
) -> bytes:
    commands: list[str] = []
    commands.append("1 1 1 rg 0 0 {w:.2f} {h:.2f} re f".format(w=plan.page_width, h=plan.page_height))
    _draw_title(commands, plan.title, plan.subtitle, plan.page_width, plan.page_height)
    _draw_footer(commands, page_number, page_count, plan.page_width)

    commands.append(
        "q {x:.2f} {y:.2f} {w:.2f} {h:.2f} re W n".format(
            x=plan.content_left,
            y=plan.clip_bottom,
            w=plan.content_width,
            h=plan.content_height,
        )
    )
    transform = PdfTransform(
        viewport=viewport,
        content_left=plan.content_left,
        content_top=plan.content_top,
        scale=plan.scale,
    )

    nodes_by_id = {node.id: node for node in layout.nodes}
    for edge in layout.edges:
        start_node = nodes_by_id.get(edge.from_id)
        end_node = nodes_by_id.get(edge.to_id)
        if start_node and end_node and _bounds_intersect(_edge_bounds(start_node, end_node, edge.kind), viewport):
            _draw_edge(commands, start_node, end_node, edge.label, edge.kind, transform)

    for node in layout.nodes:
        if _bounds_intersect(_node_bounds(node), viewport):
            _draw_node(commands, node, transform)

    commands.append("Q")
    return "\n".join(commands).encode("latin-1", "replace")


def _pdf_objects(page_width: float, page_height: float, page_contents: list[bytes]) -> list[bytes]:
    page_count = len(page_contents)
    page_ids = list(range(3, 3 + page_count))
    font_id = 3 + page_count
    content_start_id = font_id + 1
    kids = " ".join(f"{page_id} 0 R" for page_id in page_ids)

    objects: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        f"<< /Type /Pages /Kids [{kids}] /Count {page_count} >>".encode("ascii"),
    ]

    for index, page_id in enumerate(page_ids):
        content_id = content_start_id + index
        objects.append(
            (
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {page_width:.2f} {page_height:.2f}] "
                f"/Resources << /Font << /F1 {font_id} 0 R >> >> /Contents {content_id} 0 R >>"
            ).encode("ascii")
        )

    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    for content in page_contents:
        objects.append(b"<< /Length " + str(len(content)).encode("ascii") + b" >>\nstream\n" + content + b"\nendstream")
    return objects


def _draw_title(commands: list[str], title: str, subtitle: str, page_width: float, page_height: float) -> None:
    font_size = 18
    x = (page_width - _text_width(title, font_size)) / 2
    y = page_height - 34 if subtitle else page_height - 38
    commands.append("0.12 0.16 0.19 rg")
    commands.append(_text_command(title, x, y, font_size))
    if subtitle:
        subtitle_size = 10
        subtitle_x = (page_width - _text_width(subtitle, subtitle_size)) / 2
        commands.append("0.36 0.41 0.44 rg")
        commands.append(_text_command(subtitle, subtitle_x, page_height - 52, subtitle_size))


def _draw_footer(commands: list[str], page_number: int, page_count: int, page_width: float) -> None:
    if page_count <= 1:
        return
    label = f"Page {page_number} of {page_count}"
    font_size = 9
    commands.append("0.36 0.41 0.44 rg")
    commands.append(_text_command(label, (page_width - _text_width(label, font_size)) / 2, 20, font_size))


def _draw_node(
    commands: list[str],
    node: NodeLayout,
    transform: PdfTransform,
) -> None:
    definition = SHAPE_DEFINITIONS[node.type]
    fill = _rgb(definition.fill)
    outline = _rgb(definition.outline)
    left, top = transform.point(node.left, node.top)
    right, bottom = transform.point(node.right, node.bottom)
    center_x, center_y = transform.point(node.x, node.y)
    width = right - left
    height = top - bottom

    commands.append(f"{fill} rg {outline} RG 1.2 w")
    if node.shape == "oval":
        commands.append(_ellipse_path(center_x, center_y, width / 2, height / 2) + " B")
    elif node.shape == "diamond":
        points = [
            (center_x, center_y + height / 2),
            (center_x + width / 2, center_y),
            (center_x, center_y - height / 2),
            (center_x - width / 2, center_y),
        ]
        commands.append(_polygon_path(points) + " B")
    elif node.shape == "parallelogram":
        slant = transform.length(22)
        points = [
            (left + slant, bottom + height),
            (left + width, bottom + height),
            (left + width - slant, bottom),
            (left, bottom),
        ]
        commands.append(_polygon_path(points) + " B")
    else:
        commands.append(f"{left:.2f} {bottom:.2f} {width:.2f} {height:.2f} re B")

    commands.append(_centered_multiline_text(node.label, center_x, center_y, max(8.0, 11 * transform.scale)))


def _draw_edge(
    commands: list[str],
    start_node: NodeLayout,
    end_node: NodeLayout,
    label: str,
    kind: EdgeKind,
    transform: PdfTransform,
) -> None:
    if kind == EdgeKind.LOOP:
        _draw_loop_edge(commands, start_node, end_node, label, transform)
        return
    layout_start_x, layout_start_y, layout_end_x, layout_end_y = _edge_points_layout(start_node, end_node)
    start_x, start_y = transform.point(layout_start_x, layout_start_y)
    end_x, end_y = transform.point(layout_end_x, layout_end_y)

    commands.append("0.42 0.46 0.48 RG 1.15 w")
    commands.append(f"{start_x:.2f} {start_y:.2f} m {end_x:.2f} {end_y:.2f} l S")
    commands.append(_arrowhead_path(start_x, start_y, end_x, end_y))
    if label:
        font_size = max(8.0, 10 * transform.scale)
        label_x, label_y = edge_label_anchor(start_x, start_y, end_x, end_y, label, font_size)
        commands.append("0.18 0.22 0.25 rg")
        commands.append(_text_command(label, label_x, label_y, font_size))


def _draw_loop_edge(
    commands: list[str],
    start_node: NodeLayout,
    end_node: NodeLayout,
    label: str,
    transform: PdfTransform,
) -> None:
    layout_points = _loop_points_layout(start_node, end_node)
    points = [transform.point(x, y) for x, y in layout_points]

    commands.append("0.42 0.46 0.48 RG 1.15 w")
    commands.append(_polyline_path(points) + " S")
    start_x, start_y = points[-2]
    end_x, end_y = points[-1]
    commands.append(_arrowhead_path(start_x, start_y, end_x, end_y))
    if label:
        label_start_x, label_start_y = points[0]
        label_end_x, label_end_y = points[1]
        font_size = max(8.0, 10 * transform.scale)
        label_x, label_y = edge_label_anchor(label_start_x, label_start_y, label_end_x, label_end_y, label, font_size)
        commands.append("0.18 0.22 0.25 rg")
        commands.append(_text_command(label, label_x, label_y, font_size))


def _edge_points_layout(
    start_node: NodeLayout,
    end_node: NodeLayout,
) -> tuple[float, float, float, float]:
    dx = end_node.x - start_node.x
    dy = end_node.y - start_node.y
    if abs(dx) >= abs(dy):
        start_x = start_node.right if dx >= 0 else start_node.left
        end_x = end_node.left if dx >= 0 else end_node.right
        start_y = start_node.y
        end_y = end_node.y
    else:
        start_x = start_node.x
        end_x = end_node.x
        start_y = start_node.bottom if dy >= 0 else start_node.top
        end_y = end_node.top if dy >= 0 else end_node.bottom
    return start_x, start_y, end_x, end_y


def _loop_points_layout(start_node: NodeLayout, end_node: NodeLayout) -> list[tuple[float, float]]:
    if abs(end_node.y - start_node.y) >= abs(end_node.x - start_node.x):
        offset_x = min(start_node.left, end_node.left) - LOOP_OFFSET
        return [
            (start_node.left, start_node.y),
            (offset_x, start_node.y),
            (offset_x, end_node.y),
            (end_node.left, end_node.y),
        ]
    offset_y = min(start_node.top, end_node.top) - LOOP_OFFSET
    return [
        (start_node.x, start_node.top),
        (start_node.x, offset_y),
        (end_node.x, offset_y),
        (end_node.x, end_node.top),
    ]


def _centered_multiline_text(text: str, center_x: float, center_y: float, font_size: float) -> str:
    lines = wrap_node_text(text)
    line_height = font_size + 3
    start_y = center_y + ((len(lines) - 1) * line_height / 2) - font_size / 3
    commands = ["0.14 0.20 0.23 rg"]
    for index, line in enumerate(lines):
        x = center_x - _text_width(line, font_size) / 2
        y = start_y - index * line_height
        commands.append(_text_command(line, x, y, font_size))
    return "\n".join(commands)


def _paper_size_for_layout(layout: FlowLayout) -> tuple[float, float]:
    if layout.direction.value == "LR":
        return A4_LANDSCAPE
    return A4_PORTRAIT


def _chart_bounds(layout: FlowLayout) -> ChartBounds:
    if not layout.nodes:
        return ChartBounds(0.0, 0.0, 0.0, 0.0)

    nodes_by_id = {node.id: node for node in layout.nodes}
    left = min(node.left for node in layout.nodes)
    top = min(node.top for node in layout.nodes)
    right = max(node.right for node in layout.nodes)
    bottom = max(node.bottom for node in layout.nodes)

    for edge in layout.edges:
        start_node = nodes_by_id.get(edge.from_id)
        end_node = nodes_by_id.get(edge.to_id)
        if not start_node or not end_node:
            continue
        points = _loop_points_layout(start_node, end_node) if edge.kind == EdgeKind.LOOP else [
            _edge_points_layout(start_node, end_node)[:2],
            _edge_points_layout(start_node, end_node)[2:],
        ]
        point_bounds = _points_bounds(points)
        left = min(left, point_bounds.left)
        top = min(top, point_bounds.top)
        right = max(right, point_bounds.right)
        bottom = max(bottom, point_bounds.bottom)

    return ChartBounds(left - CHART_PADDING, top - CHART_PADDING, right + CHART_PADDING, bottom + CHART_PADDING)


def _tile_viewports(bounds: ChartBounds, viewport_width: float, viewport_height: float) -> list[PrintViewport]:
    x_windows = _axis_windows(bounds.left, bounds.right, viewport_width)
    y_windows = _axis_windows(bounds.top, bounds.bottom, viewport_height)
    return [
        PrintViewport(left=x_left, top=y_top, right=x_right, bottom=y_bottom)
        for y_top, y_bottom in y_windows
        for x_left, x_right in x_windows
    ]


def _axis_windows(start: float, end: float, span: float) -> list[tuple[float, float]]:
    size = max(1.0, end - start)
    if size <= span:
        extra = (span - size) / 2
        return [(start - extra, end + extra)]

    stride = max(span - VIEWPORT_OVERLAP, span * 0.65)
    windows: list[tuple[float, float]] = []
    current = start
    while current + span < end:
        windows.append((current, current + span))
        current += stride

    final_start = end - span
    if not windows or abs(windows[-1][0] - final_start) > 1:
        windows.append((final_start, end))
    return windows


def _node_bounds(node: NodeLayout) -> ChartBounds:
    return ChartBounds(node.left, node.top, node.right, node.bottom)


def _edge_bounds(start_node: NodeLayout, end_node: NodeLayout, kind: EdgeKind) -> ChartBounds:
    points = _loop_points_layout(start_node, end_node)
    if kind != EdgeKind.LOOP:
        start_x, start_y, end_x, end_y = _edge_points_layout(start_node, end_node)
        points = [(start_x, start_y), (end_x, end_y)]
    bounds = _points_bounds(points)
    return ChartBounds(
        bounds.left - CHART_PADDING,
        bounds.top - CHART_PADDING,
        bounds.right + CHART_PADDING,
        bounds.bottom + CHART_PADDING,
    )


def _points_bounds(points: list[tuple[float, float]]) -> ChartBounds:
    return ChartBounds(
        min(x for x, _y in points),
        min(y for _x, y in points),
        max(x for x, _y in points),
        max(y for _x, y in points),
    )


def _bounds_intersect(bounds: ChartBounds, viewport: PrintViewport) -> bool:
    return not (
        bounds.right < viewport.left
        or bounds.left > viewport.right
        or bounds.bottom < viewport.top
        or bounds.top > viewport.bottom
    )


def _write_pdf(path: Path, objects: list[bytes]) -> None:
    offsets: list[int] = []
    output = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{index} 0 obj\n".encode("ascii"))
        output.extend(obj)
        output.extend(b"\nendobj\n")

    xref_at = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets:
        output.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    output.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_at}\n%%EOF\n"
        ).encode("ascii")
    )
    path.write_bytes(output)


def _rgb(hex_color: str) -> str:
    value = hex_color.lstrip("#")
    red = int(value[0:2], 16) / 255
    green = int(value[2:4], 16) / 255
    blue = int(value[4:6], 16) / 255
    return f"{red:.3f} {green:.3f} {blue:.3f}"


def _ellipse_path(cx: float, cy: float, rx: float, ry: float) -> str:
    kappa = 0.5522847498
    return (
        f"{cx + rx:.2f} {cy:.2f} m "
        f"{cx + rx:.2f} {cy + ry * kappa:.2f} {cx + rx * kappa:.2f} {cy + ry:.2f} {cx:.2f} {cy + ry:.2f} c "
        f"{cx - rx * kappa:.2f} {cy + ry:.2f} {cx - rx:.2f} {cy + ry * kappa:.2f} {cx - rx:.2f} {cy:.2f} c "
        f"{cx - rx:.2f} {cy - ry * kappa:.2f} {cx - rx * kappa:.2f} {cy - ry:.2f} {cx:.2f} {cy - ry:.2f} c "
        f"{cx + rx * kappa:.2f} {cy - ry:.2f} {cx + rx:.2f} {cy - ry * kappa:.2f} {cx + rx:.2f} {cy:.2f} c"
    )


def _polygon_path(points: list[tuple[float, float]]) -> str:
    first_x, first_y = points[0]
    commands = [f"{first_x:.2f} {first_y:.2f} m"]
    commands.extend(f"{x:.2f} {y:.2f} l" for x, y in points[1:])
    commands.append("h")
    return " ".join(commands)


def _polyline_path(points: list[tuple[float, float]]) -> str:
    first_x, first_y = points[0]
    commands = [f"{first_x:.2f} {first_y:.2f} m"]
    commands.extend(f"{x:.2f} {y:.2f} l" for x, y in points[1:])
    return " ".join(commands)


def _arrowhead_path(start_x: float, start_y: float, end_x: float, end_y: float) -> str:
    angle = atan2(end_y - start_y, end_x - start_x)
    length = 10
    spread = pi / 7
    left = (end_x - length * cos(angle - spread), end_y - length * sin(angle - spread))
    right = (end_x - length * cos(angle + spread), end_y - length * sin(angle + spread))
    path = _polygon_path([(end_x, end_y), left, right])
    return f"0.42 0.46 0.48 rg {path} f"


def _text_command(text: str, x: float, y: float, font_size: float) -> str:
    return f"BT /F1 {font_size:.2f} Tf {x:.2f} {y:.2f} Td ({_escape_pdf_text(text)}) Tj ET"


def _text_width(text: str, font_size: float) -> float:
    return len(text) * font_size * 0.52


def _escape_pdf_text(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
