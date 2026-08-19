import argparse
import json
from pathlib import Path

from benchmark.adapters.cognodb import CognoDBAdapter
from benchmark.config import (
    DATASET_NAME,
    NODE_LABEL,
    RAW_RESULTS_DIR,
    RELATIONSHIP_TYPE,
)
from benchmark.loader import load_cognodb
from benchmark.runner import BenchmarkRunner
from benchmark.workloads import CREATE_USER_INDEX
from dataset.prepare import prepare_dataset


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="CognoDB graph benchmark using the SNAP Wiki-Vote dataset."
    )
    parser.add_argument(
        "--load",
        action="store_true",
        help="Prepare the dataset, clear CognoDB, and load the full graph.",
    )
    parser.add_argument(
        "--benchmark",
        action="store_true",
        help="Run the current CognoDB read benchmark against already loaded data.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Prepare, load, and then benchmark CognoDB.",
    )
    return parser.parse_args()


def build_resources() -> dict:
    return {
        "vcpu": "not observable",
        "ram_mb": "not observable",
        "storage_gb": "not observable",
        "cpu_usage": "not observable",
        "memory_usage": "not observable",
    }


def write_results(database_name: str, output: dict) -> Path:
    path = RAW_RESULTS_DIR / f"{database_name}.json"

    with path.open("w", encoding="utf-8") as file:
        json.dump(output, file, indent=2)

    return path


def main() -> None:
    args = parse_args()

    if not (args.load or args.benchmark or args.all):
        raise SystemExit(
            "Choose one action: --load, --benchmark, or --all."
        )

    if args.load or args.all:
        prepare_dataset()

    adapter = CognoDBAdapter()
    database_name = "cognodb"
    ingestion = None

    try:
        print("Connecting to CognoDB...")
        adapter.connect()
        print("Connected.")

        if args.load or args.all:
            ingestion = load_cognodb(adapter, reset=True)

        if args.benchmark or args.all:
            adapter.execute(CREATE_USER_INDEX)

            runner = BenchmarkRunner(
                adapter=adapter,
                database_name=database_name,
            )

            run_result = runner.run(node_id="30")

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
                "resources": build_resources(),
                "metadata": {
                    "sampled_nodes": run_result["sampled_nodes"],
                    "random_seed": run_result["random_seed"],
                    "node_label": NODE_LABEL,
                    "relationship_type": RELATIONSHIP_TYPE,
                },
            }

            path = write_results(database_name, output)

            print()
            print("Benchmark complete.")
            print(f"Results written to: {path}")
            print()

            if ingestion:
                print(
                    "Ingestion: "
                    f"{ingestion['nodes']:,} nodes / "
                    f"{ingestion['relationships']:,} relationships "
                    f"in {ingestion['total_seconds']:.2f}s "
                    f"({ingestion['relationships_per_second']:.1f} rel/s)"
                )

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