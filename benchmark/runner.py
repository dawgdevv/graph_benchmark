import json
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from benchmark.config import (
    CONCURRENCY_LEVELS,
    MIXED_WORKLOAD_OPERATIONS,
    RAW_RESULTS_DIR,
    READ_ITERATIONS,
    READ_RATIO,
    RANDOM_SEED,
    SAMPLED_NODES_PATH,
    WARMUP_ITERATIONS,
)
from benchmark.metrices import summarize_latencies
from benchmark.workloads import (
    AGGREGATION,
    INDEXED_LOOKUP,
    POINT_LOOKUP,
    TRAVERSAL_1_HOP,
    TRAVERSAL_2_HOP,
    TRAVERSAL_3_HOP,
    WRITE_TICK,
)


def read_sampled_nodes() -> list[str]:
    with SAMPLED_NODES_PATH.open("r", encoding="utf-8") as file:
        return json.load(file)


class BenchmarkRunner:
    def __init__(self, adapter, database_name: str) -> None:
        self.adapter = adapter
        self.database_name = database_name
        self.rng = random.Random(RANDOM_SEED)

    def benchmark_query(
        self,
        name: str,
        query: str,
        params_fn,
    ) -> dict:
        for _ in range(WARMUP_ITERATIONS):
            self.adapter.execute(query, params_fn())

        latencies_ms: list[float] = []

        for _ in range(READ_ITERATIONS):
            start = time.perf_counter()

            self.adapter.execute(query, params_fn())

            elapsed_ms = (time.perf_counter() - start) * 1000

            latencies_ms.append(elapsed_ms)

        return {
            "workload": name,
            **summarize_latencies(latencies_ms),
        }

    def run(self, node_id: str) -> dict:
        sampled_nodes = read_sampled_nodes()

        def fixed_params() -> dict:
            return {"id": node_id}

        def traversal_params() -> dict:
            return {"id": self.rng.choice(sampled_nodes)}

        workloads = [
            (
                "point_lookup",
                POINT_LOOKUP,
                fixed_params,
            ),
            (
                "indexed_lookup",
                INDEXED_LOOKUP,
                fixed_params,
            ),
            (
                "traversal_1hop",
                TRAVERSAL_1_HOP,
                traversal_params,
            ),
            (
                "traversal_2hop",
                TRAVERSAL_2_HOP,
                traversal_params,
            ),
            (
                "traversal_3hop",
                TRAVERSAL_3_HOP,
                traversal_params,
            ),
            (
                "aggregation",
                AGGREGATION,
                lambda: {},
            ),
        ]

        results = []

        for name, query, params_fn in workloads:
            print(f"Running {name}...")

            result = self.benchmark_query(
                name=name,
                query=query,
                params_fn=params_fn,
            )

            results.append(result)

        mixed_workload = self.run_mixed_workload(sampled_nodes)

        return {
            "sampled_nodes": len(sampled_nodes),
            "random_seed": RANDOM_SEED,
            "workloads": results,
            "mixed_workload": mixed_workload,
        }

    def run_mixed_workload(self, sampled_nodes: list[str]) -> list[dict]:
        read_queries = [
            POINT_LOOKUP,
            INDEXED_LOOKUP,
            TRAVERSAL_1_HOP,
            TRAVERSAL_2_HOP,
            TRAVERSAL_3_HOP,
        ]

        levels = []

        for concurrency in CONCURRENCY_LEVELS:
            rng = random.Random(RANDOM_SEED)

            plan = []

            for _ in range(MIXED_WORKLOAD_OPERATIONS):
                node_id = rng.choice(sampled_nodes)

                if rng.random() < READ_RATIO:
                    query = rng.choice(read_queries)
                    params = {"id": node_id}
                else:
                    query = WRITE_TICK
                    params = {"id": node_id, "mark": rng.randrange(2**31)}

                plan.append((query, params))

            latencies_ms: list[float] = []
            errors = 0

            start = time.perf_counter()

            with ThreadPoolExecutor(
                max_workers=concurrency,
                thread_name_prefix=f"mixed-{concurrency}",
            ) as executor:
                futures = [
                    executor.submit(self._execute_timed, query, params)
                    for query, params in plan
                ]

                for future in as_completed(futures):
                    ok, elapsed_ms = future.result()

                    if ok:
                        latencies_ms.append(elapsed_ms)
                    else:
                        errors += 1

            duration_seconds = time.perf_counter() - start

            summary = summarize_latencies(latencies_ms) if latencies_ms else {
                "count": 0,
                "min_ms": 0.0,
                "mean_ms": 0.0,
                "p50_ms": 0.0,
                "p95_ms": 0.0,
                "p99_ms": 0.0,
                "max_ms": 0.0,
                "stddev_ms": 0.0,
            }

            operations = MIXED_WORKLOAD_OPERATIONS

            levels.append(
                {
                    "concurrency": concurrency,
                    "operations": operations,
                    "duration_seconds": round(duration_seconds, 3),
                    "throughput_qps": round(
                        operations / duration_seconds, 2
                    ),
                    "p50_ms": summary["p50_ms"],
                    "p95_ms": summary["p95_ms"],
                    "p99_ms": summary["p99_ms"],
                    "errors": errors,
                    "success_rate": round(
                        (operations - errors) / operations, 4
                    ),
                }
            )

            print(
                f"Mixed workload concurrency={concurrency}: "
                f"{operations / duration_seconds:.2f} qps, p50="
                f"{summary['p50_ms']:.2f} ms, p95="
                f"{summary['p95_ms']:.2f} ms, errors={errors}"
            )

        return levels

    def _execute_timed(self, query: str, params: dict):
        start = time.perf_counter()

        try:
            self.adapter.execute(query, params)
            return True, (time.perf_counter() - start) * 1000
        except Exception:
            return False, (time.perf_counter() - start) * 1000