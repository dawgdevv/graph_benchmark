from benchmark.adapters.cognodb import CognoDBAdapter
from benchmark.runner import BenchmarkRunner
from benchmark.workloads import CREATE_USER_INDEX


def main() -> None:
    adapter = CognoDBAdapter()

    try:
        print("Connecting to CognoDB...")

        adapter.connect()

        print("Connected.")

        print("Creating index...")

        adapter.execute(CREATE_USER_INDEX)

        runner = BenchmarkRunner(
            adapter=adapter,
            database_name="cognodb",
        )

        results = runner.run(
            node_id="30",
        )

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