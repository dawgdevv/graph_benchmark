import argparse

from benchmark.adapters.cognodb import CognoDBAdapter
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


def main() -> None:
    args = parse_args()

    if not (args.load or args.benchmark or args.all):
        raise SystemExit(
            "Choose one action: --load, --benchmark, or --all."
        )

    if args.load or args.all:
        prepare_dataset()

    adapter = CognoDBAdapter()

    try:
        print("Connecting to CognoDB...")
        adapter.connect()
        print("Connected.")

        if args.load or args.all:
            load_result = load_cognodb(adapter, reset=True)
            print(
                "Load verified: "
                f"{load_result['nodes']:,} nodes, "
                f"{load_result['relationships']:,} relationships."
            )

        if args.benchmark or args.all:
            adapter.execute(CREATE_USER_INDEX)

            runner = BenchmarkRunner(
                adapter=adapter,
                database_name="cognodb",
            )

            results = runner.run(node_id="30")

            print()
            print("Benchmark complete.")

            for result in results["workloads"]:
                print(
                    f"{result['workload']}: "
                    f"p50={result['p50_ms']:.2f} ms, "
                    f"p95={result['p95_ms']:.2f} ms"
                )

    finally:
        adapter.close()


if __name__ == "__main__":
    main()
