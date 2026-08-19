from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

DATASET_DIR = PROJECT_ROOT / "dataset"
RESULTS_DIR = PROJECT_ROOT / "results"
RAW_RESULTS_DIR = RESULTS_DIR / "raw"

RAW_DATASET_PATH = DATASET_DIR / "Wiki-Vote.txt"
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

LOAD_BATCH_SIZE = 500
# TypeDB has no UNWIND: one TypeQL query per batch, so larger batches mean fewer commits.
TYPEDB_LOAD_BATCH_SIZE = 2000

DATABASES = {
    "cognodb": {
        "label": "CognoDB Cloud",
        "resources": {
            "vcpu": "0.5 burstable",
            "ram_mb": "512",
            "storage_gb": "1",
            "cpu_usage": "not exposed by vendor",
            "memory_usage": "not exposed by vendor",
            "tier": "free c0",
            "limits": "200 connections",
            "region": "us-east4 / us-central1 / europe-west1",
        },
    },
    "neo4j": {
        "label": "Neo4j Aura Free",
        "resources": {
            "vcpu": "not published",
            "ram_mb": "not published (page cache slightly > 1 GB Professional)",
            "storage_gb": "not published",
            "cpu_usage": "not exposed by vendor",
            "memory_usage": "not exposed by vendor",
            "tier": "AuraDB Free",
            "limits": "200000 nodes / 400000 relationships; 1 instance; pause after 72h idle",
            "region": "gcp-us-central1",
        },
    },
    "memgraph": {
        "label": "Memgraph Cloud",
        "resources": {
            "vcpu": "not published (Cloud SKUs up to 8 cores)",
            "ram_mb": "2048 (~1600 usable)",
            "storage_gb": "not published",
            "cpu_usage": "not exposed by vendor",
            "memory_usage": "not exposed by vendor",
            "tier": "14-day Cloud trial",
            "limits": "1 project; snapshots disabled on trial",
            "region": "AWS (6 regions)",
        },
    },
    "falkordb": {
        "label": "FalkorDB Cloud",
        "resources": {
            "vcpu": "not published",
            "ram_mb": "100",
            "storage_gb": "in-memory (100 MB max graph)",
            "cpu_usage": "not exposed by vendor",
            "memory_usage": "not exposed by vendor",
            "tier": "free instance",
            "limits": "no TLS; no persistence; idle stop 1 day / delete 7 days",
            "region": "AWS or GCP",
        },
    },
    "typedb": {
        "label": "TypeDB Cloud",
        "resources": {
            "vcpu": "2 burstable",
            "ram_mb": "4096 (e2-medium / t4g.medium); pricing page lists 8192",
            "storage_gb": "10",
            "cpu_usage": "not exposed by vendor",
            "memory_usage": "not exposed by vendor",
            "tier": "Explore (free forever)",
            "limits": "1 free cluster per team; backups disabled",
            "region": "GCP or AWS",
        },
    },
}


def ensure_directories() -> None:
    DATASET_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    RAW_RESULTS_DIR.mkdir(parents=True, exist_ok=True)


ensure_directories()
