"""Ensure the repository root is on ``sys.path`` for test imports.

The custom ``tests`` package is located inside the workspace root
``/home/ubuntu/briefing/.worktrees/builder-ingest``.  Pytest does not pick up
the package directory automatically, so importing :mod:`app` from our test
modules fails with ``ModuleNotFoundError``.

Adding this ``conftest.py`` injects the project root into the interpreter
path before any tests run, making the ``app`` package importable.
"""

import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
