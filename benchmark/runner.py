import json
import time
from pathlib import Path

from benchmark.config import (
    RAW_RESULTS_DIR,
    READ_ITERATIONS,
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


class BenchmarkRunner:
    def __init__(self, adapter, database_name: str) -> None:
        self.adapter = adapter
        self.database_name = database_name

    def benchmark_query(
        self,
        name: str,
        query: str,
        params: dict | None = None,
    ) -> dict:
        params = params or {}

        for _ in range(WARMUP_ITERATIONS):
            self.adapter.execute(query, params)

        latencies_ms: list[float] = []

        for _ in range(READ_ITERATIONS):
            start = time.perf_counter()

            self.adapter.execute(query, params)

            elapsed_ms = (time.perf_counter() - start) * 1000

            latencies_ms.append(elapsed_ms)

        return {
            "workload": name,
            **summarize_latencies(latencies_ms),
        }

    def run(self, node_id: str) -> dict:
        workloads = [
            (
                "point_lookup",
                POINT_LOOKUP,
                {"id": node_id},
            ),
            (
                "indexed_lookup",
                INDEXED_LOOKUP,
                {"id": node_id},
            ),
            (
                "traversal_1hop",
                TRAVERSAL_1_HOP,
                {"id": node_id},
            ),
            (
                "traversal_2hop",
                TRAVERSAL_2_HOP,
                {"id": node_id},
            ),
            (
                "traversal_3hop",
                TRAVERSAL_3_HOP,
                {"id": node_id},
            ),
            (
                "aggregation",
                AGGREGATION,
                {},
            ),
        ]

        results = []

        for name, query, params in workloads:
            print(f"Running {name}...")

            result = self.benchmark_query(
                name=name,
                query=query,
                params=params,
            )

            results.append(result)

        output = {
            "database": self.database_name,
            "workloads": results,
        }

        path = RAW_RESULTS_DIR / f"{self.database_name}.json"

        with path.open("w", encoding="utf-8") as file:
            json.dump(output, file, indent=2)

        return output