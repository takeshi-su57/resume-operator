"""Orchestration flows — the blocking, prompter-driven sequences that sit
above the graph.

Each module here drives a multi-step user interaction (approval loop,
enrichment interview) via the `Prompter` seam. The CLI and the future
desktop server both import from this package; the only thing that changes
between them is which `Prompter` they construct.
"""
