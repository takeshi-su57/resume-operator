# [Feature]: Verify LangGraph graph assembly compiles and runs with parse_resume

## Description

This is the first real LangGraph exercise. Verify that `graph.py` compiles successfully and that invoking the graph with an initial state runs `parse_resume` as the first node. Write a focused integration test.

## Motivation

Before implementing more nodes, confirm that the LangGraph machinery works: StateGraph compiles, state flows through nodes, and the node return dict is merged into state correctly.

## LangGraph Concepts Introduced

- **StateGraph(Type)**: creates a graph parameterized by a state type
- **graph.add_node("name", fn)**: registers a node function
- **graph.add_edge(START, "name")**: defines flow from entry point
- **graph.compile()**: produces a runnable graph
- **compiled.invoke(state)**: executes the graph with initial state

## Tasks

- [ ] Create `tests/test_graph.py`
- [ ] Test: `test_graph_compiles` — call `build_graph()`, verify it returns without error
- [ ] Test: `test_graph_runs_parse_resume` — mock all tools, invoke graph with `resume_path` and `job_description_path` set, verify `parse_resume` was called
- [ ] Add comments explaining LangGraph concepts for future reference
- [ ] Verify the state type annotation in `graph.py` is correct

## Acceptance Criteria

- `build_graph()` compiles without error
- Graph invocation with mocked tools executes `parse_resume` node
- Test file includes brief LangGraph concept comments

## Key Files

- `tests/test_graph.py` (new)
- `src/resume_operator/graph.py`

## Dependencies

- #006

## Labels

`enhancement`, `priority:high`
