"""Test configuration.

Ensures the project root is importable so that the `api` package can be
imported when running tests via `uv run pytest` where CWD may not be on
`sys.path` by default.
"""

from pathlib import Path
import sys


def _ensure_project_root_on_path() -> None:
    project_root = Path(__file__).resolve().parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))


_ensure_project_root_on_path()
