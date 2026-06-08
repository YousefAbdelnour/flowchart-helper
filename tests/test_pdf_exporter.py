import tempfile
import unittest
from pathlib import Path

from flowchart_model import FlowDirection, Step, StepType, build_a4_paper_flow_layout, build_flow_layout, sample_steps
from pdf_exporter import create_print_plan, edge_label_anchor, export_flowchart_pdf


class PdfExportTests(unittest.TestCase):
    def test_export_writes_a_valid_pdf_file_with_flowchart_text(self) -> None:
        layout = build_flow_layout(sample_steps())

        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "sample-flowchart.pdf"
            export_flowchart_pdf(target, layout, title="A Basic Flowchart")
            content = target.read_bytes()

        self.assertTrue(content.startswith(b"%PDF-1.4"))
        self.assertIn(b"/Type /Page", content)
        self.assertIn(b"A Basic Flowchart", content)
        self.assertIn(b"Decision", content)
        self.assertIn(b"Yes", content)
        self.assertIn(b"No", content)

    def test_export_includes_optional_metadata_subtitle(self) -> None:
        layout = build_a4_paper_flow_layout(
            [Step(id="start", label="Start", type=StepType.TERMINATOR)]
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "metadata-flowchart.pdf"
            export_flowchart_pdf(target, layout, title="Lab Flow", subtitle="Youssef | CHEM 205 | Density Lab")
            content = target.read_bytes()

        self.assertIn(b"Lab Flow", content)
        self.assertIn(b"Youssef | CHEM 205 | Density Lab", content)

    def test_export_uses_single_continuous_page_for_horizontal_strips(self) -> None:
        layout = build_flow_layout(
            [
                Step(id=f"step-{index}", label=f"Step {index}", type=StepType.PROCESS)
                for index in range(1, 13)
            ],
            direction=FlowDirection.LEFT_RIGHT,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "wide-flowchart.pdf"
            export_flowchart_pdf(target, layout, title="Wide Flowchart")
            content = target.read_bytes()

        plan = create_print_plan(layout, title="Wide Flowchart")
        self.assertEqual(len(plan.viewports), 1)
        self.assertEqual(plan.scale, 1.0)
        self.assertGreater(plan.page_width, 842.0)
        self.assertEqual(content.count(b"/Type /Page /Parent"), 1)

    def test_export_uses_single_continuous_page_for_vertical_strips(self) -> None:
        layout = build_flow_layout(
            [
                Step(id=f"step-{index}", label=f"Step {index}", type=StepType.PROCESS)
                for index in range(1, 28)
            ],
            direction=FlowDirection.TOP_BOTTOM,
        )

        plan = create_print_plan(layout, title="Vertical Flowchart")

        self.assertEqual(len(plan.viewports), 1)
        self.assertEqual(plan.scale, 1.0)
        self.assertEqual(plan.page_width, 595.0)
        self.assertGreater(plan.page_height, 842.0)

    def test_print_plan_uses_a4_page_boundaries_from_wrapped_layout(self) -> None:
        layout = build_a4_paper_flow_layout(
            [
                Step(id=f"step-{index}", label=f"Step {index}", type=StepType.PROCESS)
                for index in range(1, 25)
            ]
        )

        plan = create_print_plan(layout, title="Wrapped")

        self.assertEqual((plan.page_width, plan.page_height), (595.0, 842.0))
        self.assertEqual(len(plan.viewports), layout.page_count)
        self.assertEqual(plan.scale, 1.0)

    def test_edge_label_anchor_places_vertical_labels_beside_arrow_midpoint(self) -> None:
        label_x, label_y = edge_label_anchor(100.0, 500.0, 100.0, 200.0, "No", 10)

        self.assertGreater(label_x, 100.0)
        self.assertLess(abs(label_y - 350.0), 20.0)


if __name__ == "__main__":
    unittest.main()
