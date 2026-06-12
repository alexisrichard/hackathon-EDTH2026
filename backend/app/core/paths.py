"""Path bootstrap so the backend can import the shared ``scripts`` package.

Running ``uvicorn app.main:app`` from ``backend/`` puts ``backend/`` on
``sys.path`` but not the repo root, so ``from scripts.common.bbox import ...``
would fail. Importing this module (side-effect on import) prepends the repo root,
making ``scripts`` importable as an implicit namespace package.

Import this *before* any ``scripts.*`` import.
"""

from __future__ import annotations

import sys
from pathlib import Path

# backend/app/core/paths.py -> parents[3] == repo root.
REPO_ROOT = Path(__file__).resolve().parents[3]

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
