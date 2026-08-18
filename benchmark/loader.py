import csv
import time

from benchmark.config import (
    EDGES_PATH,
    EXPECTED_NODE_COUNT,
    EXPECTED_RELATIONSHIP_COUNT,
    LOAD_BATCH_SIZE,
    NODES_PATH,
)

CLEAR_GRAPH = "MATCH (n) DETACH DELETE n"

CREATE_USER_INDEX = """
CREATE INDEX user_id_index IF NOT EXISTS
FOR (u:User)
ON (u.id)
"""

LOAD_NODES = """
UNWIND $rows AS row
CREATE (:User {id: row.id})
"""

LOAD_RELATIONSHIPS = """
UNWIND $rows AS row
MATCH (source:User {id: row.source})
MATCH (target:User {id: row.target})
CREATE (source)-[:VOTED]->(target)
"""

COUNT_NODES = "MATCH (n:User) RETURN count(n)"
COUNT_RELATIONSHIPS = "MATCH ()-[r:VOTED]->() RETURN count(r)"


def batched(rows: list[dict[str, str]], batch_size: int):
    for start in range(0, len(rows), batch_size):
        yield rows[start : start + batch_size]


def read_nodes() -> list[dict[str, str]]:
    if not NODES_PATH.exists():
        raise FileNotFoundError(
            f"Missing {NODES_PATH}. Run `python dataset/prepare.py` first."
        )

    with NODES_PATH.open("r", encoding="utf-8", newline="") as file:
        return [{"id": row["id"]} for row in csv.DictReader(file)]


def read_edges() -> list[dict[str, str]]:
    if not EDGES_PATH.exists():
        raise FileNotFoundError(
            f"Missing {EDGES_PATH}. Run `python dataset/prepare.py` first."
        )

    with EDGES_PATH.open("r", encoding="utf-8", newline="") as file:
        return [
            {"source": row["source"], "target": row["target"]}
            for row in csv.DictReader(file)
        ]


def load_cognodb(adapter, reset: bool = True) -> dict:
    nodes = read_nodes()
    edges = read_edges()

    if len(nodes) != EXPECTED_NODE_COUNT:
        raise ValueError(
            f"Node CSV contains {len(nodes)} rows; expected {EXPECTED_NODE_COUNT}."
        )

    if len(edges) != EXPECTED_RELATIONSHIP_COUNT:
        raise ValueError(
            f"Edge CSV contains {len(edges)} rows; "
            f"expected {EXPECTED_RELATIONSHIP_COUNT}."
        )

    if reset:
        print("Clearing existing CognoDB graph...")
        adapter.execute(CLEAR_GRAPH)

    print("Creating User.id index...")
    adapter.execute(CREATE_USER_INDEX)

    print(f"Loading {len(nodes):,} nodes in batches of {LOAD_BATCH_SIZE}...")
    node_start = time.perf_counter()

    loaded_nodes = 0
    for batch in batched(nodes, LOAD_BATCH_SIZE):
        adapter.execute(LOAD_NODES, {"rows": batch})
        loaded_nodes += len(batch)
        print(f"  nodes: {loaded_nodes:,}/{len(nodes):,}", end="\r")

    node_seconds = time.perf_counter() - node_start
    print()

    print(
        f"Loading {len(edges):,} relationships "
        f"in batches of {LOAD_BATCH_SIZE}..."
    )
    relationship_start = time.perf_counter()

    loaded_relationships = 0
    for batch in batched(edges, LOAD_BATCH_SIZE):
        adapter.execute(LOAD_RELATIONSHIPS, {"rows": batch})
        loaded_relationships += len(batch)
        print(
            f"  relationships: {loaded_relationships:,}/{len(edges):,}",
            end="\r",
        )

    relationship_seconds = time.perf_counter() - relationship_start
    print()

    actual_nodes = int(adapter.execute_value(COUNT_NODES) or 0)
    actual_relationships = int(adapter.execute_value(COUNT_RELATIONSHIPS) or 0)

    if actual_nodes != EXPECTED_NODE_COUNT:
        raise RuntimeError(
            f"CognoDB contains {actual_nodes} User nodes after loading; "
            f"expected {EXPECTED_NODE_COUNT}."
        )

    if actual_relationships != EXPECTED_RELATIONSHIP_COUNT:
        raise RuntimeError(
            f"CognoDB contains {actual_relationships} VOTED relationships after loading; "
            f"expected {EXPECTED_RELATIONSHIP_COUNT}."
        )

    total_seconds = node_seconds + relationship_seconds

    result = {
        "nodes": actual_nodes,
        "relationships": actual_relationships,
        "node_load_seconds": node_seconds,
        "relationship_load_seconds": relationship_seconds,
        "total_seconds": total_seconds,
        "nodes_per_second": actual_nodes / node_seconds if node_seconds else 0.0,
        "relationships_per_second": (
            actual_relationships / relationship_seconds
            if relationship_seconds
            else 0.0
        ),
    }

    print("CognoDB load complete.")
    print(f"  nodes: {actual_nodes:,}")
    print(f"  relationships: {actual_relationships:,}")
    print(f"  total load time: {total_seconds:.2f}s")
    print(f"  node throughput: {result['nodes_per_second']:.2f} nodes/s")
    print(
        "  relationship throughput: "
        f"{result['relationships_per_second']:.2f} relationships/s"
    )

    return result
