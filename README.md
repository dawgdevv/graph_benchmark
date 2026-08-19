# Graph Database Benchmarking Against CognoDB

A reproducible, honest comparison of **CognoDB Cloud** against other managed graph databases:
**Neo4j Aura Free**, **Memgraph Cloud**, and **FalkorDB Cloud** — same dataset, same workloads,
same client machine, entry/free cloud tiers only.

- Dataset: [SNAP Wiki-Vote](https://snap.stanford.edu/data/wiki-Vote.html) — 7,115 nodes, 103,689 directed edges
- Harness: Python, official drivers (Neo4j driver / FalkorDB client), one command per platform
- Results: `results/raw/<database>.json` (raw), this README (full matrix), `dashboard/app.py` (charts)

---

## 1. Platforms & resource fairness

Assignment rule: *same resources everywhere, or as close as the free/entry tiers allow.*
Each platform's **advertised** specs are recorded below; free tiers rarely publish full spec lists,
so this parity is approximate — that is itself recorded honestly in the [caveats](#8-caveats).

| Platform | Tier | vCPU | RAM | Storage | Region |
|---|---|---|---|---|---|
| CognoDB Cloud | free `c0` | 0.5 burstable | 256 MB | 1 GB | unrecorded |
| Neo4j Aura | AuraDB Free | not published | not published | not published | gcp-us-central1 |
| Memgraph Cloud | 14-day trial | not published | 2048 MB | not published | unrecorded |
| FalkorDB Cloud | free instance | not published | not published | not published | unrecorded |

The dataset (≈104k relationships) fits comfortably in the smallest allocation (CognoDB 1 GB / 256 MB).

## 2. Dataset

- Source: [SNAP Wiki-Vote](https://snap.stanford.edu/data/wiki-Vote.html) — Wikipedia administrator
  elections voting network
- **7,115 nodes**, **103,689 directed relationships** (`User` → `VOTED` → `User`)
- Prepared once into `dataset/nodes.csv` / `edges.csv` + a deterministic sample of 100 start nodes
  (`dataset/sampled_nodes.json`, seed 42) by `dataset/prepare.py`
- Identical rows loaded into every platform

**Load method (all platforms):** batched Cypher inserts via the official driver — `UNWIND $rows CREATE`
in batches of 500, one `User.id` index created before loading, graph cleared with `DETACH DELETE` before
each run.

## 3. Methodology

- **Queries:** the same logical Cypher queries on every platform (see table below)
- **Warm-up:** 20 warm-up executions per workload, **not** measured (cold numbers not reported separately)
- **Measurement:** 100 timed iterations per workload, percentiles reported (p50 / p95 / p99)
- **Start nodes:** a fixed, randomly chosen set of 100 sampled nodes (seed 42) — same nodes on all platforms
- **Mixed workload:** 1,000 operations per level at **1 / 10 / 40 concurrent clients**, 80% reads / 20% writes
  (`SET u.benchmark_mark = $mark` on a sampled node)
- **Same client machine** ran every platform; regions are whatever the free tier assigned (see caveats)

| Workload | Query (same on every platform) |
|---|---|
| Point lookup | `MATCH (u:User {id: $id}) RETURN u` |
| Indexed lookup | `MATCH (u:User) WHERE u.id = $id RETURN u` (index: `User.id`) |
| 1-hop | `MATCH (u:User {id: $id})-[:VOTED]->(v) RETURN count(v)` |
| 2-hop | `MATCH (u:User {id: $id})-[:VOTED]->()-[:VOTED]->(v) RETURN count(v)` |
| 3-hop | `MATCH (u:User {id: $id})-[:VOTED]->()-[:VOTED]->()-[:VOTED]->(v) RETURN count(v)` |
| Aggregation | `MATCH (u:User)-[:VOTED]->() RETURN u.id, count(*) AS votes ORDER BY votes DESC LIMIT 100` |
| Write tick (mix) | `MATCH (u:User {id: $id}) SET u.benchmark_mark = $mark` |

## 4. How to reproduce

Requires free accounts: [CognoDB](https://console.cognodb.com/signup), [Neo4j Aura](https://console.neo4j.io),
[Memgraph Cloud](https://cloud.memgraph.com), [FalkorDB Cloud](https://app.falkordb.cloud).

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env        # fill in credentials; never commit .env
```

Environment variables (`.env`, read by the harness via `python-dotenv`):

| Variable | Platform |
|---|---|
| `COGNODB_URI`, `COGNODB_USERNAME`, `COGNODB_PASSWORD` | `bolt+s://<instance>.databases.cognodb.cloud` |
| `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD` | `neo4j+s://xxxx.databases.neo4j.io` |
| `MEMGRAPH_URI`, `MEMGRAPH_USERNAME`, `MEMGRAPH_PASSWORD` | `bolt+ssc://<host>:7687` |
| `FALKORDB_URI`, `FALKORDB_PASSWORD` | `falkor://<username>@<host>:<port>` (native RESP) |

Run a full cycle (prepare dataset → load → benchmark) for one platform:

```bash
python main.py --db cognodb --all    # or: neo4j | memgraph | falkordb
```

Or stepwise — load only, or benchmark only (benchmark assumes data already loaded once):

```bash
python main.py --db cognodb --load
python main.py --db cognodb --benchmark
```

Every run merges into `results/raw/<database>.json` and prints ingest + per-workload percentiles.

**Dashboard** (results matrix + charts, dark theme):

```bash
streamlit run dashboard/app.py
```

## 5. Results matrix

All latency in milliseconds; lower is better for latency. Ingest and qps: higher is better.

### 5.1 Data loading

| Platform | Nodes | Relationships | Load wall-clock (s) | Nodes/s | Relationships/s | Node batch p50 (ms) | Rel batch p50 (ms) |
|---|---|---|---|---|---|---|---|
| CognoDB Cloud | 7,115 | 103,689 | 71.3 | 941 | 1,633 | 349.3 | 282.7 |
| Neo4j Aura | 7,115 | 103,689 | 23.5 | 5,053 | 4,713 | 93.0 | 102.3 |
| Memgraph Cloud | 7,115 | 103,689 | 64.6 | 1,714 | 1,722 | 276.7 | 280.8 |
| FalkorDB Cloud | 7,115 | 103,689 | 66.2 | 1,734 | 1,678 | 273.1 | 277.5 |

### 5.2 Query latency (p50 / p95)

| Workload | CognoDB p50 | CognoDB p95 | Neo4j p50 | Neo4j p95 | Memgraph p50 | Memgraph p95 | FalkorDB p50 | FalkorDB p95 |
|---|---|---|---|---|---|---|---|---|
| Point lookup | 274.6 | 278.9 | 82.1 | 224.9 | 266.5 | 286.3 | 270.7 | 320.5 |
| Indexed lookup | 274.1 | 276.4 | 81.9 | 106.9 | 265.9 | 286.1 | 270.4 | 277.6 |
| 1-hop | 274.5 | 277.2 | 81.6 | 91.3 | 265.6 | 269.2 | 271.5 | 275.3 |
| 2-hop | 274.5 | 283.7 | 82.3 | 91.1 | 266.8 | 284.0 | 273.4 | 377.0 |
| 3-hop | 281.8 | 714.9 | 83.1 | 104.2 | 269.9 | 367.9 | 270.7 | 274.8 |
| Aggregation | 369.1 | 405.9 | 100.8 | 111.1 | 308.2 | 315.7 | 302.5 | 309.7 |

### 5.3 Mixed read/write (1,000 ops, 80/20 read/write)

| Concurrency | Platform | Throughput (qps) | p50 (ms) | p95 (ms) | p99 (ms) | Errors | Success |
|---|---|---|---|---|---|---|---|
| 1 | CognoDB Cloud | 3.37 | 276.5 | 354.3 | 774.8 | 0 | 100% |
| 1 | Neo4j Aura | 11.24 | 82.6 | 98.5 | 183.6 | 0 | 100% |
| 1 | Memgraph Cloud | 3.69 | 266.3 | 275.1 | 293.5 | 0 | 100% |
| 1 | FalkorDB Cloud | 3.65 | 270.4 | 275.3 | 357.6 | 0 | 100% |
| 10 | CognoDB Cloud | 31.03 | 284.1 | 408.9 | 1,350.4 | 0 | 100% |
| 10 | Neo4j Aura | 114.54 | 82.0 | 101.4 | 120.4 | 0 | 100% |
| 10 | Memgraph Cloud | 30.50 | 287.6 | 377.4 | 970.4 | 0 | 100% |
| 10 | FalkorDB Cloud | 33.65 | 269.6 | 288.3 | 753.7 | 0 | 100% |
| 40 | CognoDB Cloud | 53.78 | 517.6 | 1,418.9 | 5,196.4 | 1 | 99.9% |
| 40 | Neo4j Aura | 341.98 | 83.3 | 512.5 | 564.6 | 0 | 100% |
| 40 | Memgraph Cloud | 129.51 | 269.9 | 290.0 | 1,429.3 | 0 | 100% |
| 40 | FalkorDB Cloud | 86.78 | 272.3 | 756.1 | 4,314.1 | 10 | 99.0% |

### 5.4 Footprint

| Platform | vCPU | RAM | Storage | CPU usage | Memory usage |
|---|---|---|---|---|---|
| CognoDB Cloud | 0.5 burstable | 256 MB | 1 GB | not observable | not observable |
| Neo4j Aura | not published | not published | not published | not observable | not observable |
| Memgraph Cloud | not published | 2048 MB | not published | not observable | not observable |
| FalkorDB Cloud | not published | not published | not published | not observable | not observable |

## 6. Analysis

**Neo4j Aura Free is markedly faster on every metric.** p50 stays ~82 ms for every lookup and traversal
depth (vs ~266–275 ms for the other three), ingestion runs at ~4.7–5.1k relationships/s (vs ~1.6–1.7k),
and the 40-client mixed workload sustains 342 qps — 2.6× Memgraph, the next best. Quiz-like p95s stay flat
with depth for Neo4j (91 → 104 ms from 1-hop to 3-hop); the others degrade (CognoDB p95 277 → 715 ms).

**The other three platforms cluster tightly around ~270 ms p50.** That clustering across three different
engines (Bolt-compatible Cypher, Redis-module GraphBLAS) smells less like engine cost and more like a
shared floor: free-tier throttling or network/region round-trip from the client machine, plus a
per-query latency composed of client → cloud round-trips. Note ingestion batch latencies (~275–350 ms per
500-row batch) sit in the same band — consistent with a round-trip-dominated floor rather than compute.

**Mixed-workload scaling separates them.** At 40 clients: Neo4j 342 qps, Memgraph 130 qps, FalkorDB
87 qps (but 10 errors, 99.0% success), CognoDB 54 qps with a p99 spike to 5.2 s and 1 error. Memgraph
scales with the least tail degradation (p99 1.4 s). CognoDB's free `c0` (0.5 burstable vCPU, 256 MB) is
the most constrained allocation and shows it under load; it was never left with a completely clean
tail — p99 5.2 s at 40 clients is a throttling signature.

**Honest read:** this is a free-tier comparison, not a fixed-hardware benchmark. The assignment demands
"same resources or as close as tiers allow" — free tiers don't publish their allocations, so part of
what we measured is each vendor's free-tier generosity. Neo4j's larger allowance explains part of its
win; the ~270 ms floor of the others is plausibly regional network + tier throttling. What is *not*
explained by hardware is Neo4j's flat p95 scaling through 3 hops, which suggests a more efficient
query path for path-length-independent lookups + index use.

## 7. Reproducibility & code quality

- `requirements.txt` pins the stack (neo4j driver, falkordb client, pandas, streamlit, numpy)
- Deterministic seed (42) for sampled start nodes; same nodes for every platform
- One command per platform: `python main.py --db <name> --all`
- Results are machine-readable JSON in `results/raw/`; dashboard renders them (charts)
- Credentials come from `.env` / environment variables only — **no secrets in the repo**
- `dataset/prepare.py` is idempotent and verified against expected counts (7,115 / 103,689) with a
  post-load verification step that fails the run on mismatches

```
graph_benchmark/
├── main.py                # CLI: --db --load --benchmark --all
├── dataset/prepare.py     # SNAP Wiki-Vote → nodes.csv / edges.csv / sampled_nodes.json
├── benchmark/
│   ├── adapters/          # one adapter per platform (Cypher drivers / RESP client)
│   ├── loader.py          # batched load + index + verification
│   ├── runner.py          # workloads, warmup/iterations, concurrency sweep
│   ├── workloads.py       # the exact queries (identical everywhere)
│   └── metrics.py         # percentile summaries
├── results/raw/           # per-platform JSON results (committed)
└── dashboard/app.py       # Streamlit results matrix + charts
```

## 8. Caveats

- **Resource parity is approximate.** Only CognoDB publishes vCPU/RAM/storage for its free tier;
  Neo4j/Memgraph/FalkorDB publish partial or no specs. Assume their allocations ≥ CognoDB's (256 MB) —
  asymmetric allocations are the main threat to fairness in this comparison.
- **Region variance.** Only Neo4j's region was recorded (gcp-us-central1). The others provision wherever
  the free tier assigned; a single region for all platforms is planned for a future run.
- **Client machine not recorded** in the JSON metadata; all runs came from the same laptop.
- **Cold start not separated.** 20 warm-up iterations were discarded; first-query (cold) numbers were
  not recorded separately.
- **Free-tier throttling observed:** CognoDB (p99 5.2 s, 1 error at 40 clients) and FalkorDB
  (10 errors, 99.0% success at 40 clients). Errors are counted and reported, not hidden.
- **No dataset caching on target**: each load starts from an empty graph (verified counts) so partial
  retries can't contaminate numbers.
- **SurrealDB** (5th candidate) still pending: its SurrealQL dialect and WS/REST protocol need a separate
  adapter; the harness is structured so one adapter per platform is all that's required to extend it.

## 9. Extension points

Add another platform by implementing `benchmark/adapters/base.py:DatabaseAdapter`
(connect / execute / execute_value / close) plus a `DATABASES` entry in `benchmark/config.py` —
the loader, runner, dashboard, and result pipeline are platform-agnostic.