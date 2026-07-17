"""Shared pytest helpers.

``load_script`` imports a standalone script by file path — used by the test
modules that cover the ``.claude/hooks/`` and ``.github/scripts/`` tooling, whose
logic lives in pure functions but whose files sit outside any importable package.
Importing only defines functions (each script's work is behind an
``if __name__ == "__main__"`` guard), so there are no side effects.
"""

import importlib.util
from pathlib import Path


def load_script(path: Path, name: str):
    """Import the module at ``path`` under ``name``, by file path."""
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
