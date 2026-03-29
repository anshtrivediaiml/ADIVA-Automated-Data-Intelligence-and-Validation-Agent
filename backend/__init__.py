"""Backend package bootstrap for consistent imports across API, scripts, and Celery."""

from __future__ import annotations

import os
import sys

_backend_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_backend_dir)

for _path in (_project_root, _backend_dir):
    if _path not in sys.path:
        sys.path.insert(0, _path)

