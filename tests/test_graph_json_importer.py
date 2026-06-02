import unittest

from flowchart_model import EdgeKind, FlowDirection, FlowNodeType, build_graph_layout
from json_importer import JsonImportError, parse_flowchart_json


LAB_GRAPH_JSON = """
{
  "version": "1.0",
  "title": "Mini Lab Flowchart",
  "nodes": [
    { "id": "start", "type": "start", "text": "Start" },
    { "id": "test", "type": "process", "text": "Add liquid to water" },
    { "id": "mix", "type": "decision", "text": "Does the liquid mix with water?" },
    { "id": "yes_record", "type": "action", "text": "Record miscible" },
    { "id": "no_record", "type": "action", "text": "Record immiscible and float/sink" },
    { "id": "density", "type": "process", "text": "Continue with density measurement" },
    { "id": "end", "type": "end", "text": "End" }
  ],
  "edges": [
    { "id": "e1", "from": "start", "to": "test" },
    { "id": "e2", "from": "test", "to": "mix" },
    { "id": "e3", "from": "mix", "to": "yes_record", "label": "Yes", "type": "yes" },
    { "id": "e4", "from": "mix", "to": "no_record", "label": "No", "type": "no" },
    { "id": "e5", "from": "yes_record", "to": "density", "type": "merge" },
    { "id": "e6", "from": "no_record", "to": "density", "type": "merge" },
    { "id": "e7", "from": "density", "to": "end" }
  ],
  "settings": {
    "direction": "TB",
    "autoLayout": true,
    "showEdgeLabels": true,
    "validateBeforeRender": true
  }
}
"""

SEPARATION_GRAPH_JSON = """
{
  "version": "1.0",
  "title": "Separation of a Mixture",
  "nodes": [
    { "id": "start", "type": "start", "text": "Start" },
    { "id": "weigh_mixture", "type": "process", "text": "Weigh mixture" },
    { "id": "remove_iron", "type": "process", "text": "Remove iron with magnet" },
    { "id": "sublime_naphthalene", "type": "process", "text": "Sublime naphthalene using hot water bath and cold finger" },
    { "id": "collect_naphthalene", "type": "process", "text": "Collect and weigh naphthalene crystals" },
    { "id": "separate_sand_plastic", "type": "process", "text": "Add water to separate floating plastic from sinking sand" },
    { "id": "filter_plastic", "type": "process", "text": "Vacuum filter, dry, and weigh plastic" },
    { "id": "dry_sand", "type": "process", "text": "Dry and weigh sand" },
    { "id": "all_separated", "type": "decision", "text": "All components separated?" },
    { "id": "cleanup", "type": "action", "text": "Clean apparatus and dispose of waste" },
    { "id": "repeat_separation", "type": "action", "text": "Repeat separation if needed" },
    { "id": "end", "type": "end", "text": "End" }
  ],
  "edges": [
    { "id": "e1", "from": "start", "to": "weigh_mixture" },
    { "id": "e2", "from": "weigh_mixture", "to": "remove_iron" },
    { "id": "e3", "from": "remove_iron", "to": "sublime_naphthalene" },
    { "id": "e4", "from": "sublime_naphthalene", "to": "collect_naphthalene" },
    { "id": "e5", "from": "collect_naphthalene", "to": "separate_sand_plastic" },
    { "id": "e6", "from": "separate_sand_plastic", "to": "filter_plastic" },
    { "id": "e7", "from": "filter_plastic", "to": "dry_sand" },
    { "id": "e8", "from": "dry_sand", "to": "all_separated" },
    { "id": "e9", "from": "all_separated", "to": "cleanup", "label": "Yes", "type": "yes" },
    { "id": "e10", "from": "all_separated", "to": "repeat_separation", "label": "No", "type": "no" },
    { "id": "e11", "from": "repeat_separation", "to": "separate_sand_plastic", "type": "loop" },
    { "id": "e12", "from": "cleanup", "to": "end" }
  ],
  "settings": {
    "direction": "TB",
    "autoLayout": true,
    "showEdgeLabels": true,
    "validateBeforeRender": true
  }
}
"""


class GraphJsonImporterTests(unittest.TestCase):
    def test_parses_node_edge_graph_with_direction_and_edge_types(self) -> None:
        parsed = parse_flowchart_json(LAB_GRAPH_JSON)

        self.assertEqual(parsed.title, "Mini Lab Flowchart")
        self.assertIsNotNone(parsed.graph)
        assert parsed.graph is not None
        self.assertEqual(parsed.graph.direction, FlowDirection.TOP_BOTTOM)
        self.assertEqual(parsed.graph.nodes[0].type, FlowNodeType.START)
        self.assertEqual(parsed.graph.edges[2].kind, EdgeKind.YES)
        self.assertEqual(parsed.graph.edges[3].kind, EdgeKind.NO)
        self.assertEqual(parsed.error_issues, [])

    def test_graph_layout_keeps_yes_and_no_branches_parallel_before_merge(self) -> None:
        parsed = parse_flowchart_json(LAB_GRAPH_JSON)
        assert parsed.graph is not None

        layout = build_graph_layout(parsed.graph)
        nodes = {node.id: node for node in layout.nodes}

        self.assertLess(nodes["mix"].y, nodes["yes_record"].y)
        self.assertLess(nodes["mix"].y, nodes["no_record"].y)
        self.assertEqual(nodes["yes_record"].y, nodes["no_record"].y)
        self.assertLess(nodes["yes_record"].y, nodes["density"].y)
        self.assertLess(nodes["no_record"].y, nodes["density"].y)
        self.assertNotEqual(nodes["yes_record"].x, nodes["no_record"].x)

    def test_left_to_right_direction_rotates_graph_flow(self) -> None:
        parsed = parse_flowchart_json(LAB_GRAPH_JSON.replace('"direction": "TB"', '"direction": "LR"'))
        assert parsed.graph is not None

        layout = build_graph_layout(parsed.graph)
        nodes = {node.id: node for node in layout.nodes}

        self.assertLess(nodes["mix"].x, nodes["yes_record"].x)
        self.assertLess(nodes["mix"].x, nodes["no_record"].x)
        self.assertEqual(nodes["yes_record"].x, nodes["no_record"].x)
        self.assertLess(nodes["yes_record"].x, nodes["density"].x)
        self.assertLess(nodes["no_record"].x, nodes["density"].x)
        self.assertNotEqual(nodes["yes_record"].y, nodes["no_record"].y)

    def test_invalid_graph_raises_error_with_rule_id(self) -> None:
        bad_json = """
        {
          "version": "1.0",
          "title": "Bad",
          "nodes": [
            { "id": "start", "type": "start", "text": "Start" },
            { "id": "choice", "type": "decision", "text": "Choose?" },
            { "id": "end", "type": "end", "text": "End" }
          ],
          "edges": [
            { "from": "start", "to": "choice" },
            { "from": "choice", "to": "end", "label": "Yes" }
          ]
        }
        """

        with self.assertRaisesRegex(JsonImportError, "FLOW_007"):
            parse_flowchart_json(bad_json)

    def test_yes_branch_flowing_into_no_branch_warns_with_rule_id(self) -> None:
        suspicious_json = """
        {
          "version": "1.0",
          "title": "Suspicious",
          "nodes": [
            { "id": "start", "type": "start", "text": "Start" },
            { "id": "choice", "type": "decision", "text": "Is it miscible?" },
            { "id": "yes_step", "type": "action", "text": "Record miscible" },
            { "id": "no_step", "type": "action", "text": "Record immiscible" },
            { "id": "end", "type": "end", "text": "End" }
          ],
          "edges": [
            { "from": "start", "to": "choice" },
            { "from": "choice", "to": "yes_step", "label": "Yes", "type": "yes" },
            { "from": "choice", "to": "no_step", "label": "No", "type": "no" },
            { "from": "yes_step", "to": "no_step" },
            { "from": "no_step", "to": "end" }
          ]
        }
        """

        parsed = parse_flowchart_json(suspicious_json)

        self.assertIn("FLOW_009", [issue.code for issue in parsed.warning_issues])

    def test_unlabeled_loop_is_allowed_when_repeat_step_explains_it(self) -> None:
        parsed = parse_flowchart_json(SEPARATION_GRAPH_JSON)

        self.assertEqual(parsed.error_issues, [])
        self.assertNotIn("FLOW_012", [issue.code for issue in parsed.warning_issues])


if __name__ == "__main__":
    unittest.main()
