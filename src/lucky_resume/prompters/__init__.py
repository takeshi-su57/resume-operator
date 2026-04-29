"""Concrete implementations of the `Prompter` protocol.

- `RichPrompter` drives the CLI via `rich.console.Console`.
- A future `WebSocketPrompter` (Phase 1) will drive the desktop GUI.
"""

from lucky_resume.prompters.rich_prompter import RichPrompter

__all__ = ["RichPrompter"]
