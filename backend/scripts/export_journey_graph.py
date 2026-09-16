"""Export the Phase 3 workflow as a Mermaid source file.

Run from the repository root with ``python -m backend.scripts.export_journey_graph``.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from backend.app.agents.journey_graph import build_journey_graph


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    mermaid = build_journey_graph().get_graph().draw_mermaid()
    args.output.write_text(mermaid.rstrip() + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
