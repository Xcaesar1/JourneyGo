"""Idempotently initialize official LangGraph PostgreSQL checkpoint tables."""

from __future__ import annotations

from backend.app.agents.journey_graph.checkpoint import open_postgres_checkpointer


def main() -> None:
    with open_postgres_checkpointer(setup=True):
        pass
    print("LangGraph checkpoint schema is ready.")


if __name__ == "__main__":
    main()
