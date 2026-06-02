from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass, replace
from pathlib import Path
from tkinter import END, HORIZONTAL, INSERT, VERTICAL, Canvas, StringVar, Text, Tk, Toplevel
from tkinter import filedialog, messagebox, ttk

from installer_support import APP_VERSION
from flowchart_model import (
    EdgeKind,
    SHAPE_DEFINITIONS,
    FlowDirection,
    FlowGraph,
    FlowLayout,
    FlowNode,
    NodeLayout,
    Step,
    StepType,
    build_a4_paper_flow_layout,
    build_a4_paper_graph_layout,
    build_flow_layout,
    build_graph_layout,
    route_loop_edge,
    sample_steps,
    wrap_node_text,
)
from json_importer import JSON_EXAMPLE, LEGACY_JSON_EXAMPLE, JsonImportError, parse_flowchart_json
from pdf_exporter import export_flowchart_pdf


APP_TITLE = f"Flowchart Helper {APP_VERSION}"
TYPE_LABELS = {
    StepType.TERMINATOR: "Start / End",
    StepType.PROCESS: "Step / Action",
    StepType.DECISION: "Decision",
    StepType.INPUT_OUTPUT: "Input / Output",
}
LABEL_TO_TYPE = {label: step_type for step_type, label in TYPE_LABELS.items()}
LAYOUT_A4 = "A4 Paper"
LAYOUT_LABELS = {
    LAYOUT_A4: None,
    "Horizontal Strip": FlowDirection.LEFT_RIGHT,
    "Vertical Strip": FlowDirection.TOP_BOTTOM,
}

@dataclass
class StepRow:
    id: str
    label: StringVar
    type_label: StringVar


class FlowchartApp:
    def __init__(self, root: Tk) -> None:
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("1260x760")
        self.root.minsize(1000, 640)

        self.rows: list[StepRow] = []
        self.graph: FlowGraph | None = None
        self.selected_index = 0
        self.zoom = StringVar(value="100")
        self.layout_label = StringVar(value=LAYOUT_A4)
        self.title_text = StringVar(value="A Basic Flowchart")
        self.author_text = StringVar(value="")
        self.course_text = StringVar(value="")
        self.lab_text = StringVar(value="")
        self.description_text = StringVar(value="")
        self.status = StringVar(value="Ready")

        self._configure_theme()
        self._build_shell()
        self._load_sample()

    def _configure_theme(self) -> None:
        style = ttk.Style()
        if "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure("TFrame", background="#f4f7f9")
        style.configure("Panel.TFrame", background="#eef3f6")
        style.configure("Canvas.TFrame", background="#dfe8ed")
        style.configure("TLabel", background="#f4f7f9", foreground="#1d2a31", font=("Segoe UI", 10))
        style.configure("Panel.TLabel", background="#eef3f6", foreground="#1d2a31", font=("Segoe UI", 10))
        style.configure("Title.TLabel", font=("Segoe UI Semibold", 16), background="#eef3f6")
        style.configure("Small.TLabel", font=("Segoe UI", 9), foreground="#5d6a71", background="#eef3f6")
        style.configure("TButton", font=("Segoe UI", 10), padding=(10, 7))
        style.configure("Accent.TButton", font=("Segoe UI Semibold", 10), padding=(12, 8))
        style.configure("Row.TFrame", background="#ffffff")
        style.configure("Selected.Row.TFrame", background="#d9edf8")
        style.configure("Row.TLabel", background="#ffffff")
        style.configure("Selected.Row.TLabel", background="#d9edf8")

    def _build_shell(self) -> None:
        self.root.columnconfigure(1, weight=1)
        self.root.rowconfigure(0, weight=1)

        sidebar = ttk.Frame(self.root, style="Panel.TFrame", width=372, padding=(16, 16, 14, 12))
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_propagate(False)
        sidebar.rowconfigure(3, weight=1)

        ttk.Label(sidebar, text=APP_TITLE, style="Title.TLabel").grid(row=0, column=0, sticky="w")
        info = ttk.Frame(sidebar, style="Panel.TFrame")
        info.grid(row=1, column=0, sticky="ew", pady=(12, 8))
        info.columnconfigure(0, weight=1)
        info.columnconfigure(1, weight=1)
        self._build_chart_info_fields(info)

        ttk.Label(sidebar, text="Steps", style="Small.TLabel").grid(row=2, column=0, sticky="w", pady=(0, 6))

        rows_frame = ttk.Frame(sidebar, style="Panel.TFrame")
        rows_frame.grid(row=3, column=0, sticky="nsew")
        rows_frame.columnconfigure(0, weight=1)
        rows_frame.rowconfigure(0, weight=1)

        self.row_canvas = Canvas(rows_frame, background="#eef3f6", highlightthickness=0, width=340)
        self.row_canvas.grid(row=0, column=0, sticky="nsew")
        row_scroll = ttk.Scrollbar(rows_frame, orient=VERTICAL, command=self.row_canvas.yview)
        row_scroll.grid(row=0, column=1, sticky="ns")
        self.row_canvas.configure(yscrollcommand=row_scroll.set)

        self.row_inner = ttk.Frame(self.row_canvas, style="Panel.TFrame")
        self.row_window = self.row_canvas.create_window((0, 0), window=self.row_inner, anchor="nw")
        self.row_inner.bind("<Configure>", self._sync_row_scroll)
        self.row_canvas.bind("<Configure>", self._sync_row_width)

        controls = ttk.Frame(sidebar, style="Panel.TFrame")
        controls.grid(row=4, column=0, sticky="ew", pady=(12, 0))
        for column in range(3):
            controls.columnconfigure(column, weight=1)

        ttk.Button(controls, text="+ Step", command=self._add_step).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ttk.Button(controls, text="+ Decision", command=self._add_decision).grid(row=0, column=1, sticky="ew", padx=3)
        ttk.Button(controls, text="+ End", command=self._add_end).grid(row=0, column=2, sticky="ew", padx=(6, 0))
        ttk.Button(controls, text="Move Up", command=self._move_selected_up).grid(row=1, column=0, sticky="ew", padx=(0, 6), pady=(8, 0))
        ttk.Button(controls, text="Move Down", command=self._move_selected_down).grid(row=1, column=1, sticky="ew", padx=3, pady=(8, 0))
        ttk.Button(controls, text="Delete", command=self._delete_selected).grid(row=1, column=2, sticky="ew", padx=(6, 0), pady=(8, 0))

        footer = ttk.Frame(sidebar, style="Panel.TFrame")
        footer.grid(row=5, column=0, sticky="ew", pady=(14, 0))
        footer.columnconfigure(0, weight=1)
        footer.columnconfigure(1, weight=1)
        ttk.Button(footer, text="Sample", command=self._load_sample).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ttk.Button(footer, text="Clear", command=self._clear_rows).grid(row=0, column=1, sticky="ew")
        ttk.Button(footer, text="Import JSON", command=self._open_json_import_dialog).grid(
            row=1, column=0, columnspan=2, sticky="ew", pady=(10, 0)
        )
        ttk.Button(footer, text="Export PDF", style="Accent.TButton", command=self._export_pdf).grid(
            row=2, column=0, columnspan=2, sticky="ew", pady=(8, 0)
        )

        main = ttk.Frame(self.root, style="Canvas.TFrame", padding=(14, 14, 14, 10))
        main.grid(row=0, column=1, sticky="nsew")
        main.columnconfigure(0, weight=1)
        main.rowconfigure(1, weight=1)

        toolbar = ttk.Frame(main, style="Canvas.TFrame")
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        toolbar.columnconfigure(8, weight=1)
        ttk.Label(toolbar, text="Preview", background="#dfe8ed", font=("Segoe UI Semibold", 13)).grid(
            row=0, column=0, sticky="w", padx=(0, 16)
        )
        ttk.Label(toolbar, text="Layout", background="#dfe8ed").grid(row=0, column=1, sticky="w", padx=(0, 6))
        layout_combo = ttk.Combobox(
            toolbar,
            textvariable=self.layout_label,
            values=list(LAYOUT_LABELS.keys()),
            state="readonly",
            width=15,
        )
        layout_combo.grid(row=0, column=2, sticky="w", padx=(0, 14))
        layout_combo.bind("<<ComboboxSelected>>", lambda _event: self._redraw())
        ttk.Button(toolbar, text="-", width=3, command=lambda: self._adjust_zoom(-10)).grid(row=0, column=3, padx=(0, 4))
        ttk.Label(toolbar, textvariable=self.zoom, background="#dfe8ed", width=5, anchor="center").grid(row=0, column=4)
        ttk.Button(toolbar, text="+", width=3, command=lambda: self._adjust_zoom(10)).grid(row=0, column=5, padx=(4, 12))
        ttk.Button(toolbar, text="Reset Zoom", command=lambda: self._set_zoom(100)).grid(row=0, column=6)
        ttk.Label(toolbar, textvariable=self.status, background="#dfe8ed", foreground="#526169").grid(
            row=0, column=8, sticky="e"
        )

        canvas_frame = ttk.Frame(main, style="Canvas.TFrame")
        canvas_frame.grid(row=1, column=0, sticky="nsew")
        canvas_frame.columnconfigure(0, weight=1)
        canvas_frame.rowconfigure(0, weight=1)

        self.canvas = Canvas(canvas_frame, background="#edf2f5", highlightthickness=1, highlightbackground="#c8d4db")
        self.canvas.grid(row=0, column=0, sticky="nsew")
        x_scroll = ttk.Scrollbar(canvas_frame, orient=HORIZONTAL, command=self.canvas.xview)
        x_scroll.grid(row=1, column=0, sticky="ew")
        y_scroll = ttk.Scrollbar(canvas_frame, orient=VERTICAL, command=self.canvas.yview)
        y_scroll.grid(row=0, column=1, sticky="ns")
        self.canvas.configure(xscrollcommand=x_scroll.set, yscrollcommand=y_scroll.set)

    def _build_chart_info_fields(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text="Title", style="Small.TLabel").grid(row=0, column=0, sticky="w", columnspan=2)
        title_entry = ttk.Entry(parent, textvariable=self.title_text, font=("Segoe UI", 10))
        title_entry.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(2, 6))
        title_entry.bind("<KeyRelease>", lambda _event: self._redraw())

        fields = [
            ("Author", self.author_text, 2, 0),
            ("Course", self.course_text, 2, 1),
            ("Lab", self.lab_text, 4, 0),
            ("Description", self.description_text, 4, 1),
        ]
        for label, variable, row, column in fields:
            ttk.Label(parent, text=label, style="Small.TLabel").grid(row=row, column=column, sticky="w", padx=(0, 6))
            entry = ttk.Entry(parent, textvariable=variable, font=("Segoe UI", 9))
            entry.grid(row=row + 1, column=column, sticky="ew", padx=(0, 6) if column == 0 else (0, 0), pady=(2, 0))
            entry.bind("<KeyRelease>", lambda _event: self._redraw())

    def _sync_row_scroll(self, _event: object | None = None) -> None:
        self.row_canvas.configure(scrollregion=self.row_canvas.bbox("all"))

    def _sync_row_width(self, event: object) -> None:
        width = getattr(event, "width", 340)
        self.row_canvas.itemconfigure(self.row_window, width=width)

    def _load_sample(self) -> None:
        self.graph = None
        self.rows = [self._row_from_step(step) for step in sample_steps()]
        self.layout_label.set(LAYOUT_A4)
        self.title_text.set("A Basic Flowchart")
        self._set_metadata({})
        self.selected_index = 0
        self._render_rows()
        self._redraw()

    def _clear_rows(self) -> None:
        self.graph = None
        self.rows = [self._new_row("Start", StepType.TERMINATOR), self._new_row("End", StepType.TERMINATOR)]
        self.layout_label.set(LAYOUT_A4)
        self.title_text.set("Flowchart")
        self._set_metadata({})
        self.selected_index = 0
        self._render_rows()
        self._redraw()

    def _add_step(self) -> None:
        self.graph = None
        self._insert_after_selection(self._new_row("New step", StepType.PROCESS))

    def _add_decision(self) -> None:
        self.graph = None
        self._insert_after_selection(self._new_row("Decision", StepType.DECISION))

    def _add_end(self) -> None:
        self.graph = None
        self._insert_after_selection(self._new_row("End", StepType.TERMINATOR))

    def _insert_after_selection(self, row: StepRow) -> None:
        insert_at = min(self.selected_index + 1, len(self.rows))
        self.rows.insert(insert_at, row)
        self.selected_index = insert_at
        self._render_rows()
        self._redraw()

    def _delete_selected(self) -> None:
        self.graph = None
        if not self.rows:
            return
        self.rows.pop(self.selected_index)
        self.selected_index = min(self.selected_index, max(0, len(self.rows) - 1))
        self._render_rows()
        self._redraw()

    def _move_selected_up(self) -> None:
        self.graph = None
        if self.selected_index <= 0:
            return
        self.rows[self.selected_index - 1], self.rows[self.selected_index] = (
            self.rows[self.selected_index],
            self.rows[self.selected_index - 1],
        )
        self.selected_index -= 1
        self._render_rows()
        self._redraw()

    def _move_selected_down(self) -> None:
        self.graph = None
        if self.selected_index >= len(self.rows) - 1:
            return
        self.rows[self.selected_index + 1], self.rows[self.selected_index] = (
            self.rows[self.selected_index],
            self.rows[self.selected_index + 1],
        )
        self.selected_index += 1
        self._render_rows()
        self._redraw()

    def _render_rows(self) -> None:
        for child in self.row_inner.winfo_children():
            child.destroy()

        for index, row in enumerate(self.rows):
            selected = index == self.selected_index
            style = "Selected.Row.TFrame" if selected else "Row.TFrame"
            label_style = "Selected.Row.TLabel" if selected else "Row.TLabel"
            frame = ttk.Frame(self.row_inner, style=style, padding=(9, 8))
            frame.grid(row=index, column=0, sticky="ew", pady=(0, 8), padx=(0, 4))
            frame.columnconfigure(1, weight=1)
            frame.bind("<Button-1>", lambda _event, i=index: self._select_row(i))

            number = ttk.Label(frame, text=str(index + 1), width=3, anchor="center", style=label_style)
            number.grid(row=0, column=0, rowspan=2, sticky="nsw", padx=(0, 8))
            number.bind("<Button-1>", lambda _event, i=index: self._select_row(i))

            entry = ttk.Entry(frame, textvariable=row.label, font=("Segoe UI", 10))
            entry.grid(row=0, column=1, sticky="ew")
            entry.bind("<KeyRelease>", lambda _event: self._redraw())
            entry.bind("<FocusIn>", lambda _event, i=index: self._select_row(i, redraw_rows=False))

            combo = ttk.Combobox(
                frame,
                textvariable=row.type_label,
                values=list(LABEL_TO_TYPE.keys()),
                state="readonly",
                font=("Segoe UI", 10),
            )
            combo.grid(row=1, column=1, sticky="ew", pady=(6, 0))
            combo.bind("<<ComboboxSelected>>", lambda _event: self._redraw())
            combo.bind("<FocusIn>", lambda _event, i=index: self._select_row(i, redraw_rows=False))

        self.row_inner.columnconfigure(0, weight=1)
        self._sync_row_scroll()

    def _select_row(self, index: int, redraw_rows: bool = True) -> None:
        self.selected_index = index
        if redraw_rows:
            self._render_rows()

    def _redraw(self) -> None:
        layout = self._current_layout()
        zoom = self._zoom_ratio()
        self.canvas.delete("all")
        self.canvas.configure(scrollregion=(0, 0, layout.width * zoom, layout.height * zoom))

        if not layout.nodes:
            self.status.set("No steps")
            return

        if layout.paper_width and layout.paper_height:
            self._draw_paper_pages(layout, zoom)
        else:
            self._draw_grid(layout, zoom)
        nodes_by_id = {node.id: node for node in layout.nodes}
        for edge in layout.edges:
            start_node = nodes_by_id.get(edge.from_id)
            end_node = nodes_by_id.get(edge.to_id)
            if start_node and end_node:
                self._draw_edge(start_node, end_node, edge.label, edge.kind, layout, zoom)

        for node in layout.nodes:
            self._draw_node(node, zoom)

        self.status.set(f"{len(layout.nodes)} shapes, {len(layout.edges)} arrows")

    def _draw_grid(self, layout: FlowLayout, zoom: float) -> None:
        spacing = 48 * zoom
        width = layout.width * zoom
        height = layout.height * zoom
        x = 0
        while x <= width:
            self.canvas.create_line(x, 0, x, height, fill="#f3f6f8")
            x += spacing
        y = 0
        while y <= height:
            self.canvas.create_line(0, y, width, y, fill="#f3f6f8")
            y += spacing

    def _draw_paper_pages(self, layout: FlowLayout, zoom: float) -> None:
        for page_index in range(max(1, layout.page_count)):
            left = page_index * (layout.paper_width + layout.page_gap) * zoom
            top = 0
            right = left + layout.paper_width * zoom
            bottom = layout.paper_height * zoom
            self.canvas.create_rectangle(left + 4, top + 6, right + 4, bottom + 6, fill="#d7e0e6", outline="")
            self.canvas.create_rectangle(left, top, right, bottom, fill="#ffffff", outline="#9fb0ba", width=2)
            self.canvas.create_text(
                left + 14 * zoom,
                top + 18 * zoom,
                text=f"A4 {page_index + 1}",
                anchor="w",
                fill="#71808a",
                font=("Segoe UI", max(8, int(8 * zoom))),
            )

    def _draw_node(self, node: NodeLayout, zoom: float) -> None:
        definition = SHAPE_DEFINITIONS[node.type]
        left = node.left * zoom
        top = node.top * zoom
        right = node.right * zoom
        bottom = node.bottom * zoom
        center_x = node.x * zoom
        center_y = node.y * zoom

        common = {
            "fill": definition.fill,
            "outline": definition.outline,
            "width": max(1, int(1.3 * zoom)),
        }
        if node.shape == "oval":
            self.canvas.create_oval(left, top, right, bottom, **common)
        elif node.shape == "diamond":
            self.canvas.create_polygon(
                center_x,
                top,
                right,
                center_y,
                center_x,
                bottom,
                left,
                center_y,
                **common,
            )
        elif node.shape == "parallelogram":
            slant = 23 * zoom
            self.canvas.create_polygon(left + slant, top, right, top, right - slant, bottom, left, bottom, **common)
        else:
            self.canvas.create_rectangle(left, top, right, bottom, **common)

        self.canvas.create_text(
            center_x,
            center_y,
            text="\n".join(wrap_node_text(node.label)),
            fill=definition.text,
            font=("Segoe UI", max(8, int(10 * zoom)), "normal"),
            justify="center",
        )

    def _draw_edge(
        self,
        start_node: NodeLayout,
        end_node: NodeLayout,
        label: str,
        kind: EdgeKind,
        layout: FlowLayout,
        zoom: float,
    ) -> None:
        if kind == EdgeKind.LOOP:
            self._draw_loop_edge(start_node, end_node, label, layout, zoom)
            return
        start_x, start_y, end_x, end_y = self._edge_points(start_node, end_node, zoom)
        self.canvas.create_line(
            start_x,
            start_y,
            end_x,
            end_y,
            fill="#676e73",
            width=max(1, int(1.2 * zoom)),
            arrow="last",
            arrowshape=(12 * zoom, 14 * zoom, 5 * zoom),
        )
        if label:
            label_x, label_y = self._edge_label_position(start_x, start_y, end_x, end_y, zoom)
            self.canvas.create_text(
                label_x,
                label_y,
                text=label,
                fill="#2c3439",
                font=("Segoe UI", max(8, int(9 * zoom))),
            )

    def _draw_loop_edge(
        self,
        start_node: NodeLayout,
        end_node: NodeLayout,
        label: str,
        layout: FlowLayout,
        zoom: float,
    ) -> None:
        loop_points = [(x * zoom, y * zoom) for x, y in route_loop_edge(start_node, end_node, layout)]
        points = [coordinate for point in loop_points for coordinate in point]
        self.canvas.create_line(
            *points,
            fill="#676e73",
            width=max(1, int(1.2 * zoom)),
            arrow="last",
            arrowshape=(12 * zoom, 14 * zoom, 5 * zoom),
        )
        if label:
            label_start_x, label_start_y = loop_points[1]
            label_end_x, label_end_y = loop_points[2]
            label_x, label_y = self._edge_label_position(label_start_x, label_start_y, label_end_x, label_end_y, zoom)
            self.canvas.create_text(
                label_x,
                label_y,
                text=label,
                fill="#2c3439",
                font=("Segoe UI", max(8, int(9 * zoom))),
            )

    def _edge_label_position(
        self,
        start_x: float,
        start_y: float,
        end_x: float,
        end_y: float,
        zoom: float,
    ) -> tuple[float, float]:
        mid_x = start_x + (end_x - start_x) * 0.55
        mid_y = start_y + (end_y - start_y) * 0.55
        if abs(end_x - start_x) >= abs(end_y - start_y):
            return mid_x, mid_y - 14 * zoom
        return mid_x + 16 * zoom, mid_y

    def _edge_points(self, start_node: NodeLayout, end_node: NodeLayout, zoom: float) -> tuple[float, float, float, float]:
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
        return start_x * zoom, start_y * zoom, end_x * zoom, end_y * zoom

    def _export_pdf(self) -> None:
        layout = self._current_layout()
        if not layout.nodes:
            messagebox.showwarning(APP_TITLE, "Add at least one labeled step before exporting.")
            return

        default_path = Path.home() / "Documents" / "flowchart.pdf"
        target = filedialog.asksaveasfilename(
            title="Export flowchart as PDF",
            defaultextension=".pdf",
            initialdir=str(default_path.parent),
            initialfile=default_path.name,
            filetypes=[("PDF files", "*.pdf")],
        )
        if not target:
            return

        try:
            written = export_flowchart_pdf(target, layout, title=self._chart_title(), subtitle=self._chart_subtitle())
        except OSError as exc:
            messagebox.showerror(APP_TITLE, f"Could not export PDF:\n{exc}")
            return

        self.status.set(f"Exported {written.name}")
        if messagebox.askyesno(APP_TITLE, f"PDF exported:\n{written}\n\nOpen it now?"):
            self._open_file(written)

    def _open_json_import_dialog(self) -> None:
        dialog = Toplevel(self.root)
        dialog.title("Import Flowchart JSON")
        dialog.geometry("760x560")
        dialog.minsize(620, 420)
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.columnconfigure(0, weight=1)
        dialog.rowconfigure(1, weight=1)

        header = ttk.Frame(dialog, padding=(16, 14, 16, 8))
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text="Import JSON", font=("Segoe UI Semibold", 15)).grid(row=0, column=0, sticky="w")
        ttk.Label(
            header,
            text='Paste graph JSON with "nodes" and "edges" for real branches, or use legacy "steps" JSON for straight-line charts.',
            foreground="#5d6a71",
        ).grid(row=1, column=0, sticky="w", pady=(6, 0))

        editor_frame = ttk.Frame(dialog, padding=(16, 0, 16, 0))
        editor_frame.grid(row=1, column=0, sticky="nsew")
        editor_frame.columnconfigure(0, weight=1)
        editor_frame.rowconfigure(0, weight=1)
        text = Text(
            editor_frame,
            wrap="word",
            undo=True,
            font=("Consolas", 10),
            background="#fbfdfe",
            foreground="#172026",
            insertbackground="#172026",
            relief="solid",
            borderwidth=1,
        )
        text.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(editor_frame, orient=VERTICAL, command=text.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        text.configure(yscrollcommand=scroll.set)
        text.insert("1.0", JSON_EXAMPLE)
        text.focus_set()

        actions = ttk.Frame(dialog, padding=(16, 12, 16, 14))
        actions.grid(row=2, column=0, sticky="ew")
        actions.columnconfigure(3, weight=1)

        ttk.Button(actions, text="Load File", command=lambda: self._load_json_file_into_text(text)).grid(
            row=0, column=0, padx=(0, 8)
        )
        ttk.Button(actions, text="Reset Example", command=lambda: self._replace_text(text, JSON_EXAMPLE)).grid(
            row=0, column=1, padx=(0, 8)
        )
        ttk.Button(actions, text="Legacy Example", command=lambda: self._replace_text(text, LEGACY_JSON_EXAMPLE)).grid(
            row=0, column=2, padx=(0, 8)
        )
        ttk.Button(actions, text="Cancel", command=dialog.destroy).grid(row=0, column=4, padx=(8, 0))
        ttk.Button(
            actions,
            text="Import",
            style="Accent.TButton",
            command=lambda: self._import_json_from_text(text, dialog),
        ).grid(row=0, column=5, padx=(8, 0))

    def _load_json_file_into_text(self, text: Text) -> None:
        path = filedialog.askopenfilename(
            title="Open flowchart JSON",
            filetypes=[("JSON files", "*.json"), ("Text files", "*.txt"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            content = Path(path).read_text(encoding="utf-8")
        except OSError as exc:
            messagebox.showerror(APP_TITLE, f"Could not read JSON file:\n{exc}")
            return
        self._replace_text(text, content)

    def _import_json_from_text(self, text: Text, dialog: Toplevel) -> None:
        raw_json = text.get("1.0", END).strip()
        try:
            parsed = parse_flowchart_json(raw_json)
        except JsonImportError as exc:
            messagebox.showerror(APP_TITLE, str(exc), parent=dialog)
            return

        self.graph = parsed.graph if parsed.is_graph_json else None
        self.rows = [self._row_from_step(step) for step in parsed.steps]
        self.title_text.set(parsed.title)
        self._set_metadata(parsed.metadata)
        if parsed.graph is not None:
            self.layout_label.set(LAYOUT_A4)
        self.selected_index = 0
        self._render_rows()
        self._redraw()
        dialog.destroy()
        if parsed.warning_issues:
            messagebox.showwarning(
                APP_TITLE,
                "\n".join(f"{issue.code}: {issue.message}" for issue in parsed.warning_issues),
                parent=self.root,
            )

    def _replace_text(self, text: Text, content: str) -> None:
        text.delete("1.0", END)
        text.insert(INSERT, content)

    def _set_metadata(self, metadata: dict[str, str]) -> None:
        self.author_text.set(metadata.get("author", ""))
        self.course_text.set(metadata.get("course", ""))
        self.lab_text.set(metadata.get("lab", ""))
        self.description_text.set(metadata.get("description", ""))

    def _open_file(self, path: Path) -> None:
        if sys.platform.startswith("win"):
            subprocess.Popen(["cmd", "/c", "start", "", str(path)], shell=False)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])

    def _chart_title(self) -> str:
        return self.title_text.get().strip() or "Flowchart"

    def _chart_subtitle(self) -> str:
        parts = [
            self.author_text.get().strip(),
            self.course_text.get().strip(),
            self.lab_text.get().strip(),
        ]
        subtitle = " | ".join(part for part in parts if part)
        description = self.description_text.get().strip()
        if subtitle and description:
            return f"{subtitle} | {description}"
        return subtitle or description

    def _current_layout(self) -> FlowLayout:
        if self._uses_a4_layout():
            if self.graph is not None:
                return build_a4_paper_graph_layout(self._current_graph(FlowDirection.TOP_BOTTOM))
            return build_a4_paper_flow_layout(self._current_steps())
        direction = self._selected_direction()
        if self.graph is not None:
            return build_graph_layout(self._current_graph(direction))
        return build_flow_layout(self._current_steps(), direction=direction)

    def _current_steps(self) -> list[Step]:
        return [
            Step(id=row.id, label=row.label.get(), type=LABEL_TO_TYPE.get(row.type_label.get(), StepType.PROCESS))
            for row in self.rows
        ]

    def _current_graph(self, direction: FlowDirection) -> FlowGraph:
        assert self.graph is not None
        labels_by_id = {row.id: row.label.get() for row in self.rows}
        nodes = [
            replace(node, text=labels_by_id.get(node.id, node.text))
            for node in self.graph.nodes
        ]
        return replace(self.graph, nodes=nodes, direction=direction)

    def _selected_direction(self) -> FlowDirection:
        selected = LAYOUT_LABELS.get(self.layout_label.get())
        return selected or FlowDirection.LEFT_RIGHT

    def _uses_a4_layout(self) -> bool:
        return self.layout_label.get() == LAYOUT_A4

    def _row_from_step(self, step: Step) -> StepRow:
        return StepRow(id=step.id, label=StringVar(value=step.label), type_label=StringVar(value=TYPE_LABELS[step.type]))

    def _new_row(self, label: str, step_type: StepType) -> StepRow:
        return StepRow(
            id=f"step-{len(self.rows) + 1}",
            label=StringVar(value=label),
            type_label=StringVar(value=TYPE_LABELS[step_type]),
        )

    def _adjust_zoom(self, delta: int) -> None:
        value = int(self.zoom.get()) + delta
        self._set_zoom(value)

    def _set_zoom(self, value: int) -> None:
        clamped = max(60, min(160, value))
        self.zoom.set(str(clamped))
        self._redraw()

    def _zoom_ratio(self) -> float:
        return int(self.zoom.get()) / 100


def main() -> None:
    root = Tk()
    app = FlowchartApp(root)
    if "--smoke-test" in sys.argv:
        root.update_idletasks()
        print(app.status.get())
        root.destroy()
        return
    root.mainloop()


if __name__ == "__main__":
    main()
