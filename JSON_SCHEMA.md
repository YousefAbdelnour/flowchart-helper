# Flowchart JSON Parser Structure

Use the graph format for production flowcharts:

```json
{
  "version": "1.0",
  "title": "Flowchart Title",
  "metadata": {
    "author": "",
    "course": "",
    "lab": "",
    "description": ""
  },
  "nodes": [
    {
      "id": "unique_node_id",
      "type": "start",
      "text": "Displayed text",
      "description": "Optional longer explanation",
      "position": { "x": 0, "y": 0 }
    }
  ],
  "edges": [
    {
      "id": "unique_edge_id",
      "from": "source_node_id",
      "to": "target_node_id",
      "label": "Yes",
      "condition": "Optional condition",
      "type": "yes"
    }
  ],
  "settings": {
    "direction": "TB",
    "autoLayout": true,
    "showEdgeLabels": true,
    "validateBeforeRender": true
  }
}
```

Supported directions:

- `TB` for top-to-bottom
- `LR` for left-to-right

The app preview defaults to `A4 Paper` layout, which wraps nodes into A4 columns for printing. The `direction` setting is still used when the user switches to a straight `Horizontal Strip` or `Vertical Strip` layout.

Supported node types:

- `start`: oval, no incoming edges
- `end`: oval, no outgoing edges
- `process` or `action`: rectangle
- `decision`: diamond, at least two outgoing labeled branches
- `input`, `output`, or `input/output`: parallelogram
- `note`: rendered as a process-style note for now
- `connector`: rendered as a process-style connector for now

Supported edge types:

- `normal`
- `yes`
- `no`
- `loop`
- `merge`

Validation rule IDs:

- `FLOW_001`: must have exactly one start node
- `FLOW_002`: must have at least one end node
- `FLOW_003`: every node must have a unique id
- `FLOW_004`: every edge must reference existing node ids
- `FLOW_005`: start node cannot have incoming edges
- `FLOW_006`: end node cannot have outgoing edges
- `FLOW_007`: decision nodes must have at least two outgoing edges
- `FLOW_008`: decision outgoing edges should have labels
- `FLOW_009`: Yes and No branches should not point to each other
- `FLOW_010`: all nodes should be reachable from the start node
- `FLOW_011`: every non-end path should continue to an end node or intentional loop
- `FLOW_012`: loop edges should be clearly labeled
- `FLOW_013`: node text should not be empty
- `FLOW_014`: node text should be concise
- `FLOW_015`: decision text should be written as a question

Legacy `steps` JSON is still accepted for straight-line charts. It is converted into nodes and sequential edges internally.
