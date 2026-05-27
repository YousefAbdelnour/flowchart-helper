import unittest

from flowchart_model import StepType
from json_importer import JsonImportError, parse_flowchart_json


class JsonImporterTests(unittest.TestCase):
    def test_parses_object_with_steps_array(self) -> None:
        parsed = parse_flowchart_json(
            """
            {
              "title": "Titration Flow",
              "metadata": {
                "author": "Youssef",
                "course": "CHEM 205",
                "lab": "Density Lab",
                "description": "Manual chart info"
              },
              "steps": [
                {"id": "start", "text": "Start", "type": "start"},
                {"text": "Measure sample", "type": "step"},
                {"text": "Color changed?", "type": "decision"},
                {"text": "Record result", "type": "action"},
                {"text": "End", "type": "end"}
              ]
            }
            """
        )

        self.assertEqual(parsed.title, "Titration Flow")
        self.assertEqual(parsed.metadata["author"], "Youssef")
        self.assertEqual(parsed.metadata["course"], "CHEM 205")
        self.assertEqual(parsed.metadata["lab"], "Density Lab")
        self.assertEqual(parsed.metadata["description"], "Manual chart info")
        self.assertEqual([step.label for step in parsed.steps], ["Start", "Measure sample", "Color changed?", "Record result", "End"])
        self.assertEqual(
            [step.type for step in parsed.steps],
            [StepType.TERMINATOR, StepType.PROCESS, StepType.DECISION, StepType.PROCESS, StepType.TERMINATOR],
        )
        self.assertEqual(parsed.steps[1].id, "measure-sample")

    def test_parses_plain_array_and_input_output_alias(self) -> None:
        parsed = parse_flowchart_json(
            """
            [
              {"label": "Start", "type": "terminator"},
              {"label": "Enter volume", "type": "input/output"},
              {"label": "Calculate", "type": "process"},
              {"label": "End", "type": "terminator"}
            ]
            """
        )

        self.assertEqual(parsed.title, "Flowchart")
        self.assertEqual(parsed.steps[1].type, StepType.INPUT_OUTPUT)

    def test_rejects_invalid_json_with_clear_message(self) -> None:
        with self.assertRaisesRegex(JsonImportError, "valid JSON"):
            parse_flowchart_json("{ bad json")

    def test_rejects_step_without_label(self) -> None:
        with self.assertRaisesRegex(JsonImportError, "Step 1 needs"):
            parse_flowchart_json("""{"steps": [{"type": "step"}]}""")

    def test_rejects_unknown_type_with_allowed_values(self) -> None:
        with self.assertRaisesRegex(JsonImportError, "Unknown type"):
            parse_flowchart_json("""{"steps": [{"label": "Start", "type": "circle"}]}""")


if __name__ == "__main__":
    unittest.main()
