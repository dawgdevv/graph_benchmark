import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from benchmark.adapters.cognodb import CognoDBAdapter
from benchmark.config import (
    EDGES_PATH,
    NODES_PATH,
    NODE_LABEL,
    RELATIONSHIP_TYPE,
)

BATCH_SIZE = 10_000

INSERT_NODES = f"""
UNWIND $batch AS row
CREATE (:{NODE_LABEL} {{id: row.id}})
"""

INSERT_EDGES = f"""
UNWIND $batch AS row
MATCH (a:{NODE_LABEL} {{id: row.source}})
MATCH (b:{NODE_LABEL} {{id: row.target}})
CREATE (a)-[:{RELATIONSHIP_TYPE}]->(b)
"""


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)

        return [dict(row) for row in reader]


def chunks(items: list, size: int):
    for index in range(0, len(items), size):
        yield items[index : index + size]


def load_nodes(adapter: CognoDBAdapter, nodes: list[dict]) -> None:
    for batch in chunks(nodes, BATCH_SIZE):
        adapter.execute(INSERT_NODES, {"batch": batch})

    print(f"Loaded {len(nodes)} nodes.")


def load_edges(adapter: CognoDBAdapter, edges: list[dict]) -> None:
    for batch in chunks(edges, BATCH_SIZE):
        adapter.execute(INSERT_EDGES, {"batch": batch})

    print(f"Loaded {len(edges)} relationships.")


def load_dataset() -> None:
    nodes = read_csv_rows(NODES_PATH)
    edges = read_csv_rows(EDGES_PATH)

    print(f"Reading {NODES_PATH}: {len(nodes)} rows")
    print(f"Reading {EDGES_PATH}: {len(edges)} rows")

    adapter = CognoDBAdapter()

    try:
        print("Connecting to CognoDB...")

        adapter.connect()

        existing_count = adapter.execute_value(
            "MATCH (n) RETURN count(n) AS count"
        )

        if existing_count:
            raise RuntimeError(
                f"Database already contains {existing_count} nodes. "
                "Clear the database before loading."
            )

        print(f"Loading {NODE_LABEL} nodes...")

        load_nodes(adapter, nodes)

        print(f"Loading {RELATIONSHIP_TYPE} relationships...")

        load_edges(adapter, edges)

        node_count = adapter.execute_value(
            "MATCH (n) RETURN count(n) AS count"
        )
        relationship_count = adapter.execute_value(
            "MATCH ()-[r]->() RETURN count(r) AS count"
        )

        print()
        print("Dataset load complete.")
        print(f"Nodes: {node_count}")
        print(f"Relationships: {relationship_count}")
    finally:
        adapter.close()


if __name__ == "__main__":
    load_dataset()
