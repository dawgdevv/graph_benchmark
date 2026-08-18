import json
import random
import time
from pathlib import Path

from benchmark.config import (
    RAW_RESULTS_DIR,
    READ_ITERATIONS,
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

        output = {
            "database": self.database_name,
            "sampled_nodes": len(sampled_nodes),
            "random_seed": RANDOM_SEED,
            "workloads": results,
        }

        path = RAW_RESULTS_DIR / f"{self.database_name}.json"

        with path.open("w", encoding="utf-8") as file:
            json.dump(output, file, indent=2)

        return output