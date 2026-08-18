import csv
import json
import random

from benchmark.config import (
    RAW_DATASET_PATH,
    NODES_PATH,
    EDGES_PATH,
    SAMPLED_NODES_PATH,
    EXPECTED_NODE_COUNT,
    EXPECTED_RELATIONSHIP_COUNT,
    RANDOM_SEED,
    START_NODE_SAMPLE_SIZE,
)


def read_edges() -> list[tuple[str, str]]:
    if not RAW_DATASET_PATH.exists():
        raise FileNotFoundError(
            f"Dataset not found at {RAW_DATASET_PATH}. "
            "Run dataset/download.py first."
        )

    edges: list[tuple[str, str]] = []

    with RAW_DATASET_PATH.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            line = line.strip()

            if not line or line.startswith("#"):
                continue

            parts = line.split()

            if len(parts) != 2:
                raise ValueError(
                    f"Invalid dataset row at line {line_number}: {line!r}"
                )

            source, target = parts
            edges.append((source, target))

    return edges


def build_nodes(edges: list[tuple[str, str]]) -> list[str]:
    nodes = {node_id for edge in edges for node_id in edge}
    return sorted(nodes, key=int)


def validate_dataset(nodes: list[str], edges: list[tuple[str, str]]) -> None:
    if len(nodes) != EXPECTED_NODE_COUNT:
        raise ValueError(
            f"Unexpected node count: expected {EXPECTED_NODE_COUNT}, got {len(nodes)}"
        )

    if len(edges) != EXPECTED_RELATIONSHIP_COUNT:
        raise ValueError(
            "Unexpected relationship count: "
            f"expected {EXPECTED_RELATIONSHIP_COUNT}, got {len(edges)}"
        )


def write_nodes(nodes: list[str]) -> None:
    with NODES_PATH.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["id"])
        writer.writerows([[node_id] for node_id in nodes])


def write_edges(edges: list[tuple[str, str]]) -> None:
    with EDGES_PATH.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["source", "target"])
        writer.writerows(edges)


def write_sampled_nodes(edges: list[tuple[str, str]]) -> None:
    outgoing_nodes = sorted({source for source, _ in edges}, key=int)

    if len(outgoing_nodes) < START_NODE_SAMPLE_SIZE:
        raise ValueError(
            f"Need {START_NODE_SAMPLE_SIZE} traversal start nodes, "
            f"but only {len(outgoing_nodes)} have outgoing edges."
        )

    random_generator = random.Random(RANDOM_SEED)
    sampled_nodes = random_generator.sample(
        outgoing_nodes,
        START_NODE_SAMPLE_SIZE,
    )

    with SAMPLED_NODES_PATH.open("w", encoding="utf-8") as file:
        json.dump(sampled_nodes, file, indent=2)


def prepare_dataset() -> None:
    print(f"Reading {RAW_DATASET_PATH}...")

    edges = read_edges()
    nodes = build_nodes(edges)

    validate_dataset(nodes, edges)

    write_nodes(nodes)
    write_edges(edges)
    write_sampled_nodes(edges)

    print(f"Prepared {len(nodes)} nodes and {len(edges)} relationships.")
    print(f"Nodes CSV: {NODES_PATH}")
    print(f"Edges CSV: {EDGES_PATH}")
    print(f"Sampled nodes: {SAMPLED_NODES_PATH}")


if __name__ == "__main__":
    prepare_dataset()
