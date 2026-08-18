from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

DATASET_DIR = PROJECT_ROOT / "dataset"
RESULTS_DIR = PROJECT_ROOT / "results"
RAW_RESULTS_DIR = RESULTS_DIR / "raw"

RAW_DATASET_PATH = DATASET_DIR / "wiki-Vote.txt"
NODES_PATH = DATASET_DIR / "nodes.csv"
EDGES_PATH = DATASET_DIR / "edges.csv"
SAMPLED_NODES_PATH = DATASET_DIR / "sampled_nodes.json"

DATASET_NAME = "SNAP Wiki-Vote"

EXPECTED_NODE_COUNT = 7115
EXPECTED_RELATIONSHIP_COUNT = 103689

NODE_LABEL = "User"
RELATIONSHIP_TYPE = "VOTED"

RANDOM_SEED = 42
START_NODE_SAMPLE_SIZE = 100

WARMUP_ITERATIONS = 20
READ_ITERATIONS = 100

CONCURRENCY_LEVELS = [1, 10, 40]

MIXED_WORKLOAD_OPERATIONS = 1000
READ_RATIO = 0.80
WRITE_RATIO = 0.20


def ensure_directories() -> None:
    DATASET_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    RAW_RESULTS_DIR.mkdir(parents=True, exist_ok=True)


ensure_directories()