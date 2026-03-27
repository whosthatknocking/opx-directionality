from __future__ import annotations

import sys
from pathlib import Path

try:
    from opx.viewer import main
except ModuleNotFoundError:  # pragma: no cover - local repo execution fallback
    ROOT = Path(__file__).resolve().parents[1]
    SRC = ROOT / "src"
    if str(SRC) not in sys.path:
        sys.path.insert(0, str(SRC))
    from opx.viewer import main


if __name__ == "__main__":
    raise SystemExit(main())
