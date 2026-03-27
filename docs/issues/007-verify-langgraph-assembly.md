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

- [x] Create `tests/test_graph.py`
- [x] Test: `test_graph_compiles` — call `build_graph()`, verify it returns a `CompiledStateGraph` with all 6 expected nodes
- [x] Test: `test_graph_runs_parse_resume` — mock `extract_text` and `get_llm`, invoke graph with `resume_path` and `job_description_text`, verify `parse_resume` executes and state is merged
- [x] Add comments explaining LangGraph concepts for future reference
- [x] Verify the state type annotation in `graph.py` is correct (`CompiledStateGraph[Any]`)

## Acceptance Criteria

- `build_graph()` compiles without error
- Graph invocation with mocked tools executes `parse_resume` node
- Test file includes brief LangGraph concept comments

## Implementation Details

- `tests/test_graph.py` contains `TestGraphAssembly` class with 2 tests
- `test_graph_compiles`: verifies `build_graph()` returns `CompiledStateGraph` and filters `__start__`/`__end__` to assert all 6 user-defined nodes are registered
- `test_graph_runs_parse_resume`: mocks `extract_text` and `get_llm`, invokes full pipeline, asserts `parse_resume` output (`ResumeData`, `JobDescription`) is merged into state by LangGraph
- Module docstring documents LangGraph concepts: `StateGraph`, `add_node`, `add_edge`, `compile`, `invoke`, and stub node behavior
- `graph.py` state type annotation confirmed correct: `StateGraph(ResumeOptimizerState)` with `CompiledStateGraph[Any]` return type

## Key Files

- `tests/test_graph.py` (new)
- `src/resume_operator/graph.py` (no changes needed)

## Dependencies

- #006

## Labels

`enhancement`, `priority:high`
