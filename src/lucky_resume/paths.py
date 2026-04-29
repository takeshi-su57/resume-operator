"""Resolve filesystem paths the sidecar reads/writes at runtime.

The sidecar runs in two very different environments:

- **Dev:** launched from the repo root via ``uv run lucky-resume-server``.
  ``cwd`` is the repo, so a relative ``.env`` works.
- **MSI install:** launched by the Tauri shell from the installation
  directory. ``cwd`` is whatever the OS picks for the launched process
  (typically the install dir), and the repo isn't even on disk.

To make Settings save/load work in both modes, the env file lives at
the per-user app config dir resolved by ``platformdirs``:

- Windows:  ``%APPDATA%\\lucky-resume\\.env``
- macOS:    ``~/Library/Application Support/lucky-resume/.env``
- Linux:    ``~/.config/lucky-resume/.env``

Override for tests / dev tinkering by setting ``RESUME_OPERATOR_ENV_FILE``.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

from platformdirs import user_config_path

_APP_NAME = "lucky-resume"
_ENV_OVERRIDE_VAR = "RESUME_OPERATOR_ENV_FILE"


def env_file_path() -> Path:
    """Return the absolute path of the runtime ``.env`` file.

    Resolution order (first match wins):

    1. ``RESUME_OPERATOR_ENV_FILE`` env var — explicit override for tests
       and dev tinkering.
    2. ``./.env`` if it exists in the current working directory — keeps
       ``uv run lucky-resume-server`` from the repo root pointing at
       the developer's hand-edited ``.env`` (the legacy behavior, before
       the per-user config dir was introduced).
    3. ``user_config_path(...) / ".env"`` — the MSI install lives here
       (cwd is the install dir, no repo ``.env`` nearby).

    On Windows, step 3 resolves to ``%APPDATA%\\lucky-resume\\.env``.
    `roaming=True` picks the Roaming AppData (survives a roaming-profile
    sync) and `appauthor=False` strips platformdirs' default author
    directory so we don't end up with ``…\\lucky-resume\\lucky-resume\\``."""

    override = os.environ.get(_ENV_OVERRIDE_VAR)
    if override:
        return Path(override).expanduser().resolve()
    cwd_env = Path(".env").resolve()
    if cwd_env.is_file():
        return cwd_env
    return user_config_path(_APP_NAME, appauthor=False, roaming=True) / ".env"


def ensure_env_file() -> Path:
    """Make sure the env file exists and return its path.

    On first launch the parent directory and the file itself are
    created. If a sibling ``.env.example`` ships alongside the package
    (or lives in the repo root during dev), it's copied as the seed so
    the user lands on a Settings page with sensible defaults rather
    than a blank slate. Otherwise an empty file is touched."""

    path = env_file_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return path

    seed = _find_env_example()
    if seed is not None:
        shutil.copyfile(seed, path)
    else:
        path.touch()
    return path


def _find_env_example() -> Path | None:
    """Locate a ``.env.example`` to seed from.

    Two layouts to handle:

    - **Dev / source checkout:** the file lives at the repo root,
      three ``parent`` hops up from this module (``paths.py`` →
      ``lucky_resume/`` → ``src/`` → repo root).
    - **PyInstaller bundle:** the file is bundled as a data file under
      ``sys._MEIPASS`` (set by PyInstaller at runtime). The build script
      is responsible for adding ``--add-data .env.example:.``."""

    here = Path(__file__).resolve()
    candidates = [
        here.parent.parent.parent / ".env.example",  # dev checkout
    ]

    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(Path(meipass) / ".env.example")

    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None
