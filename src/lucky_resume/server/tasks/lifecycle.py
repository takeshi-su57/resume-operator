"""Startup hook — reconcile on-disk task records after a sidecar restart.

Any task that was `running` or `awaiting_input` when the process died
is now stranded: no asyncio task is driving it, no thread is waiting
for input. We mark them `interrupted` so the UI can surface a clear
"this didn't finish" state with a Restart button (Phase 6).

Tasks already in a terminal state (`completed`, `failed`, `cancelled`,
`interrupted`) are left as-is.
"""

from __future__ import annotations

import logging
import time

from lucky_resume.server.tasks import storage
from lucky_resume.server.tasks.model import TERMINAL_STATUSES

logger = logging.getLogger(__name__)


def reconcile_on_startup() -> None:
    """Sweep persisted tasks; any non-terminal one becomes `interrupted`."""
    now = time.time()
    fixed = 0
    for task in storage.list_all():
        if task.status in TERMINAL_STATUSES:
            continue
        task.status = "interrupted"
        task.pending_prompt = None
        task.ended_at = now
        if task.error is None:
            task.error = "Sidecar restarted before this task could finish."
        try:
            storage.save(task)
            fixed += 1
        except Exception as exc:
            logger.warning("could not mark task %s as interrupted: %s", task.id, exc)
    if fixed:
        logger.info("startup: marked %d non-terminal task(s) as interrupted", fixed)
