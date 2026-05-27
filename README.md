# Flowchart Helper

Flowchart Helper is a small Windows desktop app for creating printable flowcharts without manually drawing boxes and arrows.

Version: `1.0.0`

## Features

- Add flowchart steps with simple buttons.
- Choose shape types: start/end, step/action, decision, and input/output.
- Import full flowcharts from JSON, including branches, loops, and merges.
- Preview flowcharts on A4 paper boundaries.
- Automatically wrap long procedures into A4 columns to reduce wasted pages.
- Export print-ready PDF files.
- Install as a normal Windows app with no Python required.

## Download

The Windows installer is in the `release` folder:

```text
release/FlowchartHelper-1.0.0-Setup.exe
```

Run the installer, then launch Flowchart Helper from the Start Menu or desktop shortcut.

## Using The App

1. Enter the chart title and optional details such as author, course, lab, and description.
2. Add steps with the `+ Step`, `+ Decision`, and `+ End` buttons.
3. Type the text for each step.
4. Choose the shape type for each step.
5. Keep `A4 Paper` selected for printable charts.
6. Use `Export PDF` to save a print-ready PDF.

The `A4 Paper` layout is recommended for submissions because it wraps long procedures into columns and uses fewer pages. `Horizontal Strip` and `Vertical Strip` are available when a straight-line chart is preferred.

## JSON Import

Use `Import JSON` to paste or load a complete flowchart. For real branching, use the graph format:

```json
{
  "version": "1.0",
  "title": "Density Lab Flowchart",
  "metadata": {
    "author": "Youssef",
    "course": "CHEM 205",
    "lab": "Density Lab",
    "description": "Organic liquids procedure"
  },
  "nodes": [
    { "id": "start", "type": "start", "text": "Start" },
    { "id": "test", "type": "process", "text": "Add liquid to water" },
    { "id": "mix", "type": "decision", "text": "Does the liquid mix with water?" },
    { "id": "yes_record", "type": "action", "text": "Record miscible" },
    { "id": "no_record", "type": "action", "text": "Record immiscible and float/sink" },
    { "id": "continue", "type": "process", "text": "Continue density measurement" },
    { "id": "end", "type": "end", "text": "End" }
  ],
  "edges": [
    { "from": "start", "to": "test" },
    { "from": "test", "to": "mix" },
    { "from": "mix", "to": "yes_record", "label": "Yes", "type": "yes" },
    { "from": "mix", "to": "no_record", "label": "No", "type": "no" },
    { "from": "yes_record", "to": "continue", "type": "merge" },
    { "from": "no_record", "to": "continue", "type": "merge" },
    { "from": "continue", "to": "end" }
  ],
  "settings": {
    "direction": "TB"
  }
}
```

Legacy `steps` JSON is also supported for simple sequential charts.

See [JSON_SCHEMA.md](JSON_SCHEMA.md) for the full parser structure and validation rules.

## Development

Requirements:

- Windows
- Python 3.14 or newer
- `pytest`
- `pyinstaller`

Install development dependencies:

```powershell
python -m pip install -r requirements-dev.txt
```

Run tests:

```powershell
python -m pytest tests
```

Run the app from source:

```powershell
python app.py
```

Build the release installer:

```powershell
python build_release.py
```

The build writes:

```text
release/FlowchartHelper-1.0.0-Setup.exe
```
