import argparse
import json
from pathlib import Path

from benchmark.adapters import get_adapter
from benchmark.config import (
    DATABASES,
    DATASET_NAME,
    NODE_LABEL,
    RAW_RESULTS_DIR,
    RELATIONSHIP_TYPE,
)
from benchmark.loader import ensure_user_index, load_graph
from benchmark.runner import BenchmarkRunner
from dataset.prepare import prepare_dataset


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Graph benchmark against managed cloud databases using SNAP Wiki-Vote."
    )
    parser.add_argument(
        "--db",
        choices=sorted(DATABASES),
        default="cognodb",
        help="Cloud database to run. Default: cognodb.",
    )
    parser.add_argument(
        "--load",
        action="store_true",
        help="Prepare the dataset, clear the database, load the full graph, and write ingestion metrics.",
    )
    parser.add_argument(
        "--benchmark",
        action="store_true",
        help="Run the read/write benchmark against already loaded data.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Prepare, load, and then benchmark the selected database.",
    )
    return parser.parse_args()


def build_resources(database_name: str) -> dict:
    return dict(DATABASES[database_name]["resources"])


def results_path(database_name: str) -> Path:
    return RAW_RESULTS_DIR / f"{database_name}.json"


def read_results(database_name: str) -> dict:
    path = results_path(database_name)

    if not path.exists():
        return {}

    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def write_results(database_name: str, output: dict) -> Path:
    path = results_path(database_name)

    with path.open("w", encoding="utf-8") as file:
        json.dump(output, file, indent=2, default=_json_default)

    return path


def _json_default(value):
    if hasattr(value, "item"):
        return value.item()
    raise TypeError(f"{type(value).__name__} is not JSON serializable")


def merge_results(database_name: str, updates: dict) -> Path:
    output = read_results(database_name)
    previous_ingestion = output.get("ingestion")
    updates = dict(updates)

    if updates.get("ingestion") is None:
        updates.pop("ingestion", None)

    output.update(updates)

    if output.get("ingestion") is None and previous_ingestion is not None:
        output["ingestion"] = previous_ingestion

    return write_results(database_name, output)


def print_ingestion(ingestion: dict) -> None:
    print(
        "Ingestion: "
        f"{ingestion['nodes']:,} nodes / "
        f"{ingestion['relationships']:,} relationships "
        f"in {ingestion['total_seconds']:.2f}s "
        f"({ingestion['relationships_per_second']:.1f} rel/s)"
    )

    node_batches = ingestion.get("node_batches")
    relationship_batches = ingestion.get("relationship_batches")

    if node_batches:
        print(
            "  node batches: "
            f"p50={node_batches['p50_ms']:.2f} ms, "
            f"p95={node_batches['p95_ms']:.2f} ms, "
            f"p99={node_batches['p99_ms']:.2f} ms"
        )

    if relationship_batches:
        print(
            "  relationship batches: "
            f"p50={relationship_batches['p50_ms']:.2f} ms, "
            f"p95={relationship_batches['p95_ms']:.2f} ms, "
            f"p99={relationship_batches['p99_ms']:.2f} ms"
        )


def main() -> None:
    args = parse_args()

    if not (args.load or args.benchmark or args.all):
        raise SystemExit(
            "Choose one action: --load, --benchmark, or --all."
        )

    if args.load or args.all:
        prepare_dataset()

    adapter = get_adapter(args.db)
    database_name = args.db
    ingestion = None

    try:
        print(f"Connecting to {DATABASES[database_name]['label']}...")
        adapter.connect()
        print("Connected.")

        if args.load or args.all:
            ingestion = load_graph(adapter, database_name, reset=True)
            path = merge_results(
                database_name,
                {
                    "database": database_name,
                    "dataset": DATASET_NAME,
                    "ingestion": ingestion,
                },
            )
            print()
            print(f"Ingestion metrics written to: {path}")
            print_ingestion(ingestion)

        if args.benchmark or args.all:
            ensure_user_index(adapter, database_name)

            runner = BenchmarkRunner(
                adapter=adapter,
                database_name=database_name,
            )

            run_result = runner.run(node_id="30")

            if ingestion is None:
                ingestion = read_results(database_name).get("ingestion")
                if ingestion is None:
                    print(
                        f"Ingestion is still null because this run did not load data. "
                        f"Do not delete results/raw/{database_name}.json. "
                        f"Run `python main.py --db {database_name} --load` once to capture ingestion metrics."
                    )

            output = {
                "database": database_name,
                "dataset": DATASET_NAME,
                "ingestion": ingestion,
                "workloads": {
                    result["workload"]: {
                        key: value
                        for key, value in result.items()
                        if key != "workload"
                    }
                    for result in run_result["workloads"]
                },
                "index": {
                    "label": NODE_LABEL,
                    "property": "id",
                    "index_name": "user_id_index",
                },
                "mixed_workload": run_result["mixed_workload"],
                "resources": build_resources(database_name),
                "metadata": {
                    "sampled_nodes": run_result["sampled_nodes"],
                    "random_seed": run_result["random_seed"],
                    "node_label": NODE_LABEL,
                    "relationship_type": RELATIONSHIP_TYPE,
                },
            }

            path = merge_results(database_name, output)
            output = read_results(database_name)
            ingestion = output.get("ingestion")

            print()
            print("Benchmark complete.")
            print(f"Results written to: {path}")
            print()

            if ingestion is not None:
                print_ingestion(ingestion)

            for name, result in output["workloads"].items():
                print(
                    f"{name}: p50={result['p50_ms']:.2f} ms, "
                    f"p95={result['p95_ms']:.2f} ms, "
                    f"p99={result['p99_ms']:.2f} ms"
                )

            print("Mixed workload (read/write throughput):")

            for level in output["mixed_workload"]:
                print(
                    f"  concurrency={level['concurrency']}: "
                    f"{level['throughput_qps']:.2f} qps, p95="
                    f"{level['p95_ms']:.2f} ms, p99="
                    f"{level['p99_ms']:.2f} ms, "
                    f"success={level['success_rate']:.2%}"
                )

            print(
                "Resources: "
                f"CPU={output['resources']['cpu_usage']}, "
                f"RAM={output['resources']['memory_usage']}"
            )

    finally:
        adapter.close()


if __name__ == "__main__":
    main()