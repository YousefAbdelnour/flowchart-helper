import unittest

from flowchart_model import (
    EdgeKind,
    SHAPE_DEFINITIONS,
    FlowDirection,
    FlowEdge,
    FlowGraph,
    FlowNode,
    FlowNodeType,
    Step,
    StepType,
    route_loop_edge,
    build_a4_paper_flow_layout,
    build_a4_paper_graph_layout,
    build_flow_layout,
    build_graph_layout,
    wrap_node_text,
    normalize_steps,
    sample_steps,
    split_decision_branches,
)


class ShapeRuleTests(unittest.TestCase):
    def test_terminator_uses_oval_for_start_and_end(self) -> None:
        definition = SHAPE_DEFINITIONS[StepType.TERMINATOR]

        self.assertEqual(definition.name, "Start / End")
        self.assertEqual(definition.shape, "oval")

    def test_process_uses_rectangle_for_steps_and_actions(self) -> None:
        definition = SHAPE_DEFINITIONS[StepType.PROCESS]

        self.assertEqual(definition.name, "Step / Action")
        self.assertEqual(definition.shape, "rectangle")

    def test_decision_uses_diamond_for_choices(self) -> None:
        definition = SHAPE_DEFINITIONS[StepType.DECISION]

        self.assertEqual(definition.name, "Decision")
        self.assertEqual(definition.shape, "diamond")


class FlowLayoutTests(unittest.TestCase):
    def test_normalize_steps_omits_empty_labels(self) -> None:
        steps = normalize_steps(
            [
                Step(id="start", label="Start", type=StepType.TERMINATOR),
                Step(id="blank", label="   ", type=StepType.PROCESS),
                Step(id="step", label="Collect sample", type=StepType.PROCESS),
            ]
        )

        self.assertEqual([step.id for step in steps], ["start", "step"])

    def test_decision_remaining_steps_split_by_terminators(self) -> None:
        branches = split_decision_branches(sample_steps()[3:])

        self.assertEqual([step.label for step in branches.yes], ["Action", "End"])
        self.assertEqual([step.label for step in branches.no], ["Action", "End"])
        self.assertEqual(branches.tail, [])

    def test_decision_remaining_steps_split_evenly_without_terminators(self) -> None:
        branches = split_decision_branches(
            [
                Step(id="yes-1", label="Add indicator", type=StepType.PROCESS),
                Step(id="yes-2", label="Record result", type=StepType.PROCESS),
                Step(id="no-1", label="Heat sample", type=StepType.PROCESS),
                Step(id="no-2", label="Repeat check", type=StepType.PROCESS),
            ]
        )

        self.assertEqual([step.id for step in branches.yes], ["yes-1", "yes-2"])
        self.assertEqual([step.id for step in branches.no], ["no-1", "no-2"])

    def test_basic_sample_draws_arrows_automatically(self) -> None:
        layout = build_flow_layout(sample_steps())

        self.assertEqual(len(layout.nodes), 7)
        edge_pairs = {(edge.from_id, edge.to_id, edge.label) for edge in layout.edges}
        self.assertIn(("start", "step", ""), edge_pairs)
        self.assertIn(("step", "decision", ""), edge_pairs)
        self.assertIn(("decision", "yes-action", "Yes"), edge_pairs)
        self.assertIn(("decision", "no-action", "No"), edge_pairs)
        self.assertIn(("yes-action", "yes-end", ""), edge_pairs)
        self.assertIn(("no-action", "no-end", ""), edge_pairs)

    def test_decision_branches_are_on_separate_lanes(self) -> None:
        layout = build_flow_layout(sample_steps())
        nodes = {node.id: node for node in layout.nodes}

        self.assertEqual(nodes["yes-action"].lane, "yes")
        self.assertEqual(nodes["no-action"].lane, "no")
        self.assertLess(nodes["yes-action"].y, nodes["no-action"].y)

    def test_linear_steps_have_only_straight_sequence_edges(self) -> None:
        layout = build_flow_layout(
            [
                Step(id="start", label="Start", type=StepType.TERMINATOR),
                Step(id="measure", label="Measure water", type=StepType.PROCESS),
                Step(id="record", label="Record mass", type=StepType.PROCESS),
                Step(id="end", label="End", type=StepType.TERMINATOR),
            ]
        )

        self.assertEqual(
            [(edge.from_id, edge.to_id, edge.label) for edge in layout.edges],
            [("start", "measure", ""), ("measure", "record", ""), ("record", "end", "")],
        )
        self.assertTrue(all(node.lane == "main" for node in layout.nodes))

    def test_long_step_text_expands_process_box_to_fit_wrapped_lines(self) -> None:
        layout = build_flow_layout(
            [
                Step(id="clean", label="Clean pipette by draining remaining drops onto paper towel", type=StepType.PROCESS)
            ]
        )
        node = layout.nodes[0]

        self.assertGreater(node.height, 76)
        self.assertLessEqual(len(max(wrap_node_text(node.label), key=len)), 18)
        self.assertGreaterEqual(node.height, len(wrap_node_text(node.label)) * 16 + 28)

    def test_long_text_expands_all_shape_types(self) -> None:
        graph = FlowGraph(
            title="Text fit",
            nodes=[
                FlowNode(id="start", type=FlowNodeType.START, text="Start with a careful safety check"),
                FlowNode(id="process", type=FlowNodeType.PROCESS, text="Clean pipette by draining remaining drops onto paper towel"),
                FlowNode(id="decision", type=FlowNodeType.DECISION, text="Does the liquid mix with water after gentle swirling?"),
                FlowNode(id="io", type=FlowNodeType.INPUT, text="Record final volume reading from graduated pipette"),
                FlowNode(id="end", type=FlowNodeType.END, text="End after all observations are recorded"),
            ],
            edges=[],
        )

        layout = build_graph_layout(graph)

        for node in layout.nodes:
            with self.subTest(node=node.id):
                self.assertGreaterEqual(node.height, len(wrap_node_text(node.label)) * 16 + 28)

    def test_vertical_graph_layout_uses_compact_rank_spacing_for_printing(self) -> None:
        nodes = [
            FlowNode(id=f"node-{index}", type=FlowNodeType.PROCESS, text=f"Step {index}")
            for index in range(1, 7)
        ]
        graph = FlowGraph(
            title="Compact",
            nodes=nodes,
            edges=[
                FlowEdge(id=f"edge-{index}", from_id=nodes[index - 1].id, to_id=nodes[index].id)
                for index in range(1, len(nodes))
            ],
            direction=FlowDirection.TOP_BOTTOM,
        )

        layout = build_graph_layout(graph)
        ordered_nodes = sorted(layout.nodes, key=lambda node: node.y)
        gaps = [
            ordered_nodes[index].y - ordered_nodes[index - 1].y
            for index in range(1, len(ordered_nodes))
        ]

        self.assertTrue(all(gap <= 210 for gap in gaps))

    def test_a4_paper_layout_wraps_long_manual_flows_into_columns(self) -> None:
        steps = [
            Step(id=f"step-{index}", label=f"Procedure step {index}", type=StepType.PROCESS)
            for index in range(1, 25)
        ]

        layout = build_a4_paper_flow_layout(steps)
        first_page_nodes = [node for node in layout.nodes if node.x < layout.paper_width]
        first_page_columns = {round(node.x) for node in first_page_nodes}

        self.assertEqual((layout.paper_width, layout.paper_height), (595.0, 842.0))
        self.assertLessEqual(layout.page_count, 2)
        self.assertGreaterEqual(len(first_page_columns), 2)
        for node in layout.nodes:
            page_left = node.page_index * (layout.paper_width + layout.page_gap)
            self.assertGreaterEqual(node.left, page_left + 24)
            self.assertLessEqual(node.right, page_left + layout.paper_width - 24)
            self.assertGreaterEqual(node.top, 70)
            self.assertLessEqual(node.bottom, layout.paper_height - 36)

    def test_a4_paper_layout_uses_serpentine_columns_to_keep_wrap_arrows_short(self) -> None:
        steps = [
            Step(id=f"step-{index}", label=f"Step {index}", type=StepType.PROCESS)
            for index in range(1, 10)
        ]

        layout = build_a4_paper_flow_layout(steps)
        nodes = {node.id: node for node in layout.nodes}
        wrap_edge = next(edge for edge in layout.edges if edge.from_id == "step-6" and edge.to_id == "step-7")

        self.assertLess(abs(nodes[wrap_edge.from_id].y - nodes[wrap_edge.to_id].y), 90)
        self.assertLess(nodes["step-1"].y, nodes["step-2"].y)
        self.assertGreater(nodes["step-7"].y, nodes["step-8"].y)

    def test_a4_loop_route_stays_inside_the_page_bounds(self) -> None:
        steps = [
            Step(id=f"step-{index}", label=f"Step {index}", type=StepType.PROCESS)
            for index in range(1, 10)
        ]

        layout = build_a4_paper_flow_layout(steps)
        nodes = {node.id: node for node in layout.nodes}
        points = route_loop_edge(nodes["step-7"], nodes["step-1"], layout)
        page_left = nodes["step-7"].page_index * (layout.paper_width + layout.page_gap)
        page_right = page_left + layout.paper_width

        self.assertEqual(nodes["step-1"].page_index, nodes["step-7"].page_index)
        self.assertGreaterEqual(min(x for x, _y in points), page_left + 24)
        self.assertLessEqual(max(x for x, _y in points), page_right - 24)

    def test_a4_loop_route_uses_printable_margin_for_separation_graph(self) -> None:
        graph = FlowGraph(
            title="Separation of a Mixture",
            nodes=[
                FlowNode(id="start", type=FlowNodeType.START, text="Start"),
                FlowNode(id="weigh_mixture", type=FlowNodeType.PROCESS, text="Weigh mixture"),
                FlowNode(id="remove_iron", type=FlowNodeType.PROCESS, text="Remove iron with magnet"),
                FlowNode(id="sublime_naphthalene", type=FlowNodeType.PROCESS, text="Sublime naphthalene using hot water bath and cold finger"),
                FlowNode(id="collect_naphthalene", type=FlowNodeType.PROCESS, text="Collect and weigh naphthalene crystals"),
                FlowNode(id="separate_sand_plastic", type=FlowNodeType.PROCESS, text="Add water to separate floating plastic from sinking sand"),
                FlowNode(id="filter_plastic", type=FlowNodeType.PROCESS, text="Vacuum filter, dry, and weigh plastic"),
                FlowNode(id="dry_sand", type=FlowNodeType.PROCESS, text="Dry and weigh sand"),
                FlowNode(id="all_separated", type=FlowNodeType.DECISION, text="All components separated?"),
                FlowNode(id="cleanup", type=FlowNodeType.ACTION, text="Clean apparatus and dispose of waste"),
                FlowNode(id="repeat_separation", type=FlowNodeType.ACTION, text="Repeat separation if needed"),
                FlowNode(id="end", type=FlowNodeType.END, text="End"),
            ],
            edges=[
                FlowEdge(id="e1", from_id="start", to_id="weigh_mixture"),
                FlowEdge(id="e2", from_id="weigh_mixture", to_id="remove_iron"),
                FlowEdge(id="e3", from_id="remove_iron", to_id="sublime_naphthalene"),
                FlowEdge(id="e4", from_id="sublime_naphthalene", to_id="collect_naphthalene"),
                FlowEdge(id="e5", from_id="collect_naphthalene", to_id="separate_sand_plastic"),
                FlowEdge(id="e6", from_id="separate_sand_plastic", to_id="filter_plastic"),
                FlowEdge(id="e7", from_id="filter_plastic", to_id="dry_sand"),
                FlowEdge(id="e8", from_id="dry_sand", to_id="all_separated"),
                FlowEdge(id="e9", from_id="all_separated", to_id="cleanup", label="Yes", kind=EdgeKind.YES),
                FlowEdge(id="e10", from_id="all_separated", to_id="repeat_separation", label="No", kind=EdgeKind.NO),
                FlowEdge(id="e11", from_id="repeat_separation", to_id="separate_sand_plastic", kind=EdgeKind.LOOP),
                FlowEdge(id="e12", from_id="cleanup", to_id="end"),
            ],
            direction=FlowDirection.TOP_BOTTOM,
        )

        layout = build_a4_paper_graph_layout(graph)
        nodes = {node.id: node for node in layout.nodes}
        points = route_loop_edge(nodes["repeat_separation"], nodes["separate_sand_plastic"], layout)
        page_left = nodes["repeat_separation"].page_index * (layout.paper_width + layout.page_gap)

        self.assertGreaterEqual(min(x for x, _y in points), page_left + 36)

    def test_a4_paper_graph_layout_wraps_imported_graph_ranks(self) -> None:
        nodes = [
            FlowNode(id=f"node-{index}", type=FlowNodeType.PROCESS, text=f"Step {index}")
            for index in range(1, 22)
        ]
        graph = FlowGraph(
            title="Imported",
            nodes=nodes,
            edges=[
                FlowEdge(id=f"edge-{index}", from_id=nodes[index - 1].id, to_id=nodes[index].id)
                for index in range(1, len(nodes))
            ],
            direction=FlowDirection.TOP_BOTTOM,
        )

        layout = build_a4_paper_graph_layout(graph)
        first_page_nodes = [node for node in layout.nodes if node.page_index == 0]
        first_page_columns = {round(node.x) for node in first_page_nodes}

        self.assertEqual((layout.paper_width, layout.paper_height), (595.0, 842.0))
        self.assertLessEqual(layout.page_count, 2)
        self.assertGreaterEqual(len(first_page_columns), 2)


if __name__ == "__main__":
    unittest.main()
