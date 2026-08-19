import csv
import json
import time

from benchmark.config import (
    DATASET_NAME,
    EDGES_PATH,
    EXPECTED_NODE_COUNT,
    EXPECTED_RELATIONSHIP_COUNT,
    LOAD_BATCH_SIZE,
    NODES_PATH,
    RAW_RESULTS_DIR,
)
from benchmark.metrices import summarize_latencies

COUNT_ALL_NODES = "MATCH (n) RETURN count(n)"
CLEAR_BATCH = "MATCH (n) WITH n LIMIT 500 DETACH DELETE n"

CREATE_USER_INDEX = """
CREATE INDEX user_id_index IF NOT EXISTS
FOR (u:User)
ON (u.id)
"""

CREATE_USER_INDEX_MEMGRAPH = "CREATE INDEX ON :User(id)"
CREATE_USER_INDEX_FALKORDB = "CREATE INDEX FOR (u:User) ON (u.id)"

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


def ensure_user_index(adapter, database_name: str) -> None:
    if database_name == "memgraph":
        query = CREATE_USER_INDEX_MEMGRAPH
    elif database_name == "falkordb":
        query = CREATE_USER_INDEX_FALKORDB
    elif database_name == "typedb":
        query = CREATE_USER_INDEX
    else:
        query = CREATE_USER_INDEX

    try:
        adapter.execute(query)
    except Exception as exc:
        text = str(exc).lower()
        if "already" in text or "exists" in text:
            return
        raise


def load_graph(adapter, database_name: str, reset: bool = True) -> dict:
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
        _clear_graph(adapter)

    print("Creating User.id index...")
    index_start = time.perf_counter()
    ensure_user_index(adapter, database_name)
    index_seconds = time.perf_counter() - index_start

    print(f"Loading {len(nodes):,} nodes in batches of {LOAD_BATCH_SIZE}...")
    node_seconds, node_batch_ms = _load_batches(
        adapter,
        LOAD_NODES,
        nodes,
        "nodes",
    )

    print(
        f"Loading {len(edges):,} relationships "
        f"in batches of {LOAD_BATCH_SIZE}..."
    )
    relationship_seconds, relationship_batch_ms = _load_batches(
        adapter,
        LOAD_RELATIONSHIPS,
        edges,
        "relationships",
    )

    actual_nodes = int(adapter.execute_value(COUNT_NODES) or 0)
    actual_relationships = int(adapter.execute_value(COUNT_RELATIONSHIPS) or 0)

    total_seconds = index_seconds + node_seconds + relationship_seconds

    result = {
        "nodes": actual_nodes,
        "relationships": actual_relationships,
        "batch_size": LOAD_BATCH_SIZE,
        "index_seconds": index_seconds,
        "node_load_seconds": node_seconds,
        "relationship_load_seconds": relationship_seconds,
        "total_seconds": total_seconds,
        "nodes_per_second": actual_nodes / node_seconds if node_seconds else 0.0,
        "relationships_per_second": (
            actual_relationships / relationship_seconds
            if relationship_seconds
            else 0.0
        ),
        "node_batches": summarize_latencies(node_batch_ms),
        "relationship_batches": summarize_latencies(relationship_batch_ms),
    }

    path = _save_ingestion(database_name, result)
    print(f"Ingestion metrics written to: {path}")

    if actual_nodes != EXPECTED_NODE_COUNT:
        raise RuntimeError(
            f"{database_name} contains {actual_nodes} User nodes after loading; "
            f"expected {EXPECTED_NODE_COUNT}."
        )

    if actual_relationships != EXPECTED_RELATIONSHIP_COUNT:
        raise RuntimeError(
            f"{database_name} contains {actual_relationships} VOTED relationships "
            f"after loading; expected {EXPECTED_RELATIONSHIP_COUNT}."
        )

    print(f"{database_name} load complete.")
    print(f"  nodes: {actual_nodes:,}")
    print(f"  relationships: {actual_relationships:,}")
    print(f"  index time: {index_seconds:.2f}s")
    print(f"  total load time: {total_seconds:.2f}s")
    print(f"  node throughput: {result['nodes_per_second']:.2f} nodes/s")
    print(
        "  relationship throughput: "
        f"{result['relationships_per_second']:.2f} relationships/s"
    )
    print(
        "  node batches: "
        f"p50={result['node_batches']['p50_ms']:.2f} ms, "
        f"p95={result['node_batches']['p95_ms']:.2f} ms, "
        f"p99={result['node_batches']['p99_ms']:.2f} ms"
    )
    print(
        "  relationship batches: "
        f"p50={result['relationship_batches']['p50_ms']:.2f} ms, "
        f"p95={result['relationship_batches']['p95_ms']:.2f} ms, "
        f"p99={result['relationship_batches']['p99_ms']:.2f} ms"
    )

    return result


def _load_batches(
    adapter,
    query: str,
    rows: list[dict[str, str]],
    label: str,
) -> tuple[float, list[float]]:
    start = time.perf_counter()
    latencies_ms: list[float] = []
    loaded = 0

    for batch in batched(rows, LOAD_BATCH_SIZE):
        batch_start = time.perf_counter()
        adapter.execute(query, {"rows": batch})
        latencies_ms.append((time.perf_counter() - batch_start) * 1000)
        loaded += len(batch)
        print(f"  {label}: {loaded:,}/{len(rows):,}", end="\r")

    print()
    return time.perf_counter() - start, latencies_ms


def _clear_graph(adapter) -> None:
    print("Clearing existing graph...")
    print("You do not need to delete the graph or results JSON by hand.")

    while True:
        remaining = int(adapter.execute_value(COUNT_ALL_NODES) or 0)
        if remaining == 0:
            break
        print(f"  remaining nodes: {remaining:,}", end="\r")
        adapter.execute(CLEAR_BATCH)

    print()


def _json_default(value):
    if hasattr(value, "item"):
        return value.item()
    raise TypeError(f"{type(value).__name__} is not JSON serializable")


def _save_ingestion(database_name: str, result: dict):
    path = RAW_RESULTS_DIR / f"{database_name}.json"
    existing = {}

    if path.exists():
        with path.open("r", encoding="utf-8") as file:
            existing = json.load(file)

    existing["database"] = database_name
    existing["dataset"] = DATASET_NAME
    existing["ingestion"] = result

    with path.open("w", encoding="utf-8") as file:
        json.dump(existing, file, indent=2, default=_json_default)

    return path
