from pathlib import Path
import json

import pandas as pd
import plotly.express as px
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "results" / "raw"

PLATFORMS = [
    ("cognodb", "CognoDB Cloud"),
    ("neo4j", "Neo4j Aura"),
    ("memgraph", "Memgraph Cloud"),
    ("falkordb", "FalkorDB Cloud"),
    ("typedb", "TypeDB Cloud"),
]

LABELS = dict(PLATFORMS)
COLORS = {
    "CognoDB Cloud": "#d95c3f",
    "Neo4j Aura": "#2fbf8f",
    "Memgraph Cloud": "#5b8fd9",
    "FalkorDB Cloud": "#d9bd70",
    "TypeDB Cloud": "#8b6bb5",
}

WORKLOADS = [
    ("point_lookup", "Point lookup"),
    ("indexed_lookup", "Indexed lookup"),
    ("traversal_1hop", "1-hop"),
    ("traversal_2hop", "2-hop"),
    ("traversal_3hop", "3-hop"),
    ("aggregation", "Aggregation"),
]

st.set_page_config(
    page_title="Graph cloud benchmark",
    page_icon="◉",
    layout="wide",
)

st.markdown(
    """
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,500;9..144,600&family=Instrument+Sans:wght@400;500;600&display=swap" rel="stylesheet">
    <style>
      :root {
        --bg: #0b0c10;
        --surface: #111319;
        --line: #262a34;
        --line-soft: #1e2129;
        --fg: #e8eaf0;
        --fg-dim: #9aa2b0;
        --fg-faint: #6f7887;
      }
      html, body, [class*="css"] { font-family: "Instrument Sans", system-ui, sans-serif; }
      body { -webkit-font-smoothing: antialiased; font-variant-numeric: tabular-nums; }
      .stApp { background: var(--bg); color: var(--fg); }
      header[data-testid="stHeader"] { background: transparent; }
      footer, #MainMenu, [data-testid="stToolbar"], [data-testid="stDecoration"], [data-testid="stStatusWidget"] { display: none !important; }
      .block-container { padding-top: 3rem; padding-bottom: 5rem; max-width: 1200px; }
      h1, h2, h3 { font-family: "Fraunces", Georgia, serif !important; color: #f2f3f7 !important; letter-spacing: -0.02em; }
      .kicker { font-size: 0.7rem; font-weight: 600; letter-spacing: 0.22em; text-transform: uppercase; color: var(--fg-faint); }
      .folio { padding-bottom: 2rem; margin-bottom: 2.4rem; border-bottom: 1px solid var(--line-soft); }
      .folio h1 { font-size: clamp(1.9rem, 4vw, 2.6rem); font-weight: 500; margin: 0.55rem 0 0; }
      .folio .hint { color: var(--fg-faint); font-size: 0.9rem; line-height: 1.6; max-width: 46rem; }
      .sec { margin: 2.1rem 0 0.15rem; }
      .sec h2 { font-size: 1.32rem; font-weight: 500; margin: 0.3rem 0 0.1rem; letter-spacing: -0.01em; }
      .hint { color: var(--fg-faint); font-size: 0.87rem; line-height: 1.55; }
      .slot { border: 1px solid var(--line); border-left-width: 3px; background: var(--surface); padding: 0.55rem 0.8rem; transition: border-color 0.15s ease; }
      .slot strong { display: block; font-family: "Fraunces", Georgia, serif; font-size: 0.92rem; font-weight: 500; color: #e4e6ec; }
      .ready { border-left-color: #2f9e77; }
      .waiting { border-left-color: var(--line); opacity: 0.5; }
      code { color: #c9d0dc !important; background: #171a21 !important; border-radius: 3px; }
      [data-testid="stPills"] [role="listbox"] { gap: 0.35rem; }
      [data-testid="stPills"] button {
        border: 1px solid var(--line); background: transparent; color: var(--fg-faint);
        font-size: 0.78rem; letter-spacing: 0.04em; padding: 0.3rem 1.05rem; border-radius: 999px;
      }
      [data-testid="stPills"] button:hover { border-color: var(--fg-dim); color: var(--fg-dim); }
      [data-testid="stPills"] button[aria-checked="true"] {
        background: var(--fg); border-color: var(--fg); color: var(--bg); font-weight: 600;
      }
      [data-testid="stDataFrame"] { background: transparent; font-size: 0.85rem; }
      [data-testid="stCaptionContainer"] { color: var(--fg-faint); }
    </style>
    """,
    unsafe_allow_html=True,
)


def load_runs() -> dict[str, dict | None]:
    runs: dict[str, dict | None] = {slug: None for slug, _ in PLATFORMS}

    if not RAW_DIR.exists():
        return runs

    for path in sorted(RAW_DIR.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        slug = path.stem.lower()
        runs[slug] = payload

    return runs


def label_for(slug: str) -> str:
    if slug in LABELS:
        return LABELS[slug]
    return slug.replace("_", " ").title()


def metric(payload: dict | None, *keys):
    cursor = payload
    for key in keys:
        if not isinstance(cursor, dict) or key not in cursor:
            return None
        cursor = cursor[key]
    return cursor


def fmt(value, unit: str = "", digits: int = 2) -> str:
    if value is None:
        return "—"
    if isinstance(value, str):
        return value
    return f"{value:,.{digits}f}{unit}"


def present_runs(runs: dict[str, dict | None]) -> list[tuple[str, dict]]:
    ordered = []
    seen = set()

    for slug, _ in PLATFORMS:
        payload = runs.get(slug)
        if payload:
            ordered.append((slug, payload))
            seen.add(slug)

    for slug, payload in runs.items():
        if slug not in seen and payload:
            ordered.append((slug, payload))

    return ordered


PLOTLY_CONFIG = {"displayModeBar": False, "responsive": True}


def style_chart(fig, y_title: str, hover: str = "%{y:,.2f}<extra>%{fullData.name}</extra>"):
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Instrument Sans", color="#9aa2b0", size=12),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.04,
            x=0,
            font=dict(size=11, color="#8b94a3"),
        ),
        margin=dict(t=44, r=10, b=18, l=10),
        yaxis_title=y_title,
        xaxis_title="",
        bargap=0.3,
        hovermode="closest",
        hoverlabel=dict(
            bgcolor="#171a21",
            bordercolor="#2c313c",
            font=dict(family="Instrument Sans", color="#e8eaf0", size=12),
        ),
    )
    fig.update_xaxes(showgrid=False, tickfont=dict(color="#7c8594"), title_font=dict(color="#9aa2b0"))
    fig.update_yaxes(gridcolor="#1c1f27", zeroline=False, tickfont=dict(color="#7c8594"), title_font=dict(color="#9aa2b0"))
    fig.update_traces(marker_line_width=0, hovertemplate=hover)
    return fig


def ingestion_frame(rows: list[tuple[str, dict]]) -> pd.DataFrame:
    records = []
    for slug, payload in rows:
        ingest = payload.get("ingestion") or {}
        records.append(
            {
                "Database": label_for(slug),
                "Nodes": ingest.get("nodes"),
                "Relationships": ingest.get("relationships"),
                "Load time (s)": ingest.get("total_seconds"),
                "Nodes / s": ingest.get("nodes_per_second"),
                "Relationships / s": ingest.get("relationships_per_second"),
                "Node batch p50 (ms)": metric(ingest, "node_batches", "p50_ms"),
                "Rel batch p50 (ms)": metric(ingest, "relationship_batches", "p50_ms"),
            }
        )
    return pd.DataFrame(records)


def latency_frame(rows: list[tuple[str, dict]], stat: str) -> pd.DataFrame:
    records = []
    for slug, payload in rows:
        workloads = payload.get("workloads") or {}
        for key, name in WORKLOADS:
            records.append(
                {
                    "Database": label_for(slug),
                    "Workload": name,
                    "Latency (ms)": metric(workloads, key, stat),
                }
            )
    return pd.DataFrame(records)


def mixed_frame(rows: list[tuple[str, dict]]) -> pd.DataFrame:
    records = []
    for slug, payload in rows:
        for level in payload.get("mixed_workload") or []:
            records.append(
                {
                    "Database": label_for(slug),
                    "Concurrency": level.get("concurrency"),
                    "Throughput (qps)": level.get("throughput_qps"),
                    "p50 (ms)": level.get("p50_ms"),
                    "p95 (ms)": level.get("p95_ms"),
                    "p99 (ms)": level.get("p99_ms"),
                    "Success": level.get("success_rate"),
                    "Errors": level.get("errors"),
                }
            )
    return pd.DataFrame(records)


def matrix_frame(rows: list[tuple[str, dict]]) -> pd.DataFrame:
    records = []
    for slug, payload in rows:
        ingest = payload.get("ingestion") or {}
        workloads = payload.get("workloads") or {}
        mixed = {level.get("concurrency"): level for level in payload.get("mixed_workload") or []}
        resources = payload.get("resources") or {}
        row = {
            "Database": label_for(slug),
            "Dataset": payload.get("dataset", "—"),
            "Nodes/s": ingest.get("nodes_per_second"),
            "Rels/s": ingest.get("relationships_per_second"),
            "Load s": ingest.get("total_seconds"),
        }
        for key, name in WORKLOADS:
            row[f"{name} p50"] = metric(workloads, key, "p50_ms")
            row[f"{name} p95"] = metric(workloads, key, "p95_ms")
        for concurrency in (1, 10, 40):
            level = mixed.get(concurrency) or {}
            row[f"Mix x{concurrency} qps"] = level.get("throughput_qps")
            row[f"Mix x{concurrency} p95"] = level.get("p95_ms")
        row["vCPU"] = resources.get("vcpu")
        row["RAM"] = resources.get("ram_mb")
        records.append(row)
    return pd.DataFrame(records)


def section(num: str, title: str, hint: str = ""):
    hint_html = f'<p class="hint">{hint}</p>' if hint else ""
    st.markdown(
        f'<div class="sec"><div class="kicker">Section {num}</div><h2>{title}</h2>{hint_html}</div>',
        unsafe_allow_html=True,
    )


runs = load_runs()
ready = present_runs(runs)
ready_slugs = {slug for slug, _ in ready}

st.markdown(
    """
    <div class="folio">
      <div class="kicker">Wexa take-home · SNAP Wiki-Vote</div>
      <h1>Graph Database Benchmarking Against CognoDB</h1>
      <p class="hint">Same dataset, same workloads, entry cloud tiers. Missing files stay empty until that platform is run into <code>results/raw/&lt;name&gt;.json</code>.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

slots = st.columns(len(PLATFORMS))
for column, (slug, name) in zip(slots, PLATFORMS):
    payload = runs.get(slug)
    state = "ready" if payload else "waiting"
    column.markdown(
        f'<div class="slot {state}"><strong>{name}</strong></div>',
        unsafe_allow_html=True,
    )

if not ready:
    st.info("No result files yet. Run `python main.py --load` then `--benchmark`, or drop JSON files into `results/raw/`.")
    st.stop()

ingest_df = ingestion_frame(ready)
mixed_df = mixed_frame(ready)
matrix = matrix_frame(ready)

section("01", "Results matrix", "Assignment metrics for every platform that has a result file. Lower latency is better; higher ingest and qps are better.")

qps_cols = [f"Mix x{c} qps" for c in (1, 10, 40)]
peak_qps = float(matrix[qps_cols].max().max()) if pd.notna(matrix[qps_cols].max().max()) else 1.0
matrix_config = {
    "Database": st.column_config.TextColumn("Database", width="medium"),
    "Dataset": st.column_config.TextColumn("Dataset", width="small"),
    "Nodes/s": st.column_config.NumberColumn("Nodes/s", format="%.0f"),
    "Rels/s": st.column_config.NumberColumn("Rels/s", format="%.0f"),
    "Load s": st.column_config.NumberColumn("Load s", format="%.1f"),
}
for _, name in WORKLOADS:
    matrix_config[f"{name} p50"] = st.column_config.NumberColumn(f"{name} p50", format="%.2f")
    matrix_config[f"{name} p95"] = st.column_config.NumberColumn(f"{name} p95", format="%.2f")
for concurrency in (1, 10, 40):
    matrix_config[f"Mix x{concurrency} qps"] = st.column_config.ProgressColumn(
        f"Mix x{concurrency} qps", min_value=0.0, max_value=peak_qps, format="%.0f"
    )
    matrix_config[f"Mix x{concurrency} p95"] = st.column_config.NumberColumn(f"Mix x{concurrency} p95", format="%.2f")
matrix_config["vCPU"] = st.column_config.TextColumn("vCPU", width="small")
matrix_config["RAM"] = st.column_config.TextColumn("RAM", width="small")
st.dataframe(matrix, hide_index=True, use_container_width=True, column_config=matrix_config)

left, right = st.columns(2)

with left:
    section("02", "Ingest throughput", "Records loaded per second.")
    if ingest_df["Relationships / s"].notna().any():
        long_ingest = ingest_df.melt(
            id_vars=["Database"],
            value_vars=["Nodes / s", "Relationships / s"],
            var_name="Metric",
            value_name="Throughput",
        ).dropna()
        fig = px.bar(
            long_ingest,
            x="Metric",
            y="Throughput",
            color="Database",
            barmode="group",
            color_discrete_map=COLORS,
        )
        st.plotly_chart(
            style_chart(fig, "records / second", "%{y:,.0f} records/s<extra>%{fullData.name}</extra>"),
            use_container_width=True,
            config=PLOTLY_CONFIG,
        )
    else:
        st.caption("No ingestion numbers in the loaded files.")

with right:
    section("03", "Load wall-clock", "Total time to load the full dataset.")
    load_df = ingest_df.dropna(subset=["Load time (s)"])
    if not load_df.empty:
        fig = px.bar(
            load_df,
            x="Database",
            y="Load time (s)",
            color="Database",
            color_discrete_map=COLORS,
        )
        fig.update_layout(showlegend=False)
        st.plotly_chart(
            style_chart(fig, "seconds", "%{y:,.1f} s<extra>%{fullData.name}</extra>"),
            use_container_width=True,
            config=PLOTLY_CONFIG,
        )
    else:
        st.caption("No load times yet.")

section("04", "Query latency", "p50 / p95 for point lookup, indexed lookup, 1–3 hop traversals, and aggregation.")
stat = st.pills(
    "Percentile",
    ["p50_ms", "p95_ms"],
    format_func=lambda value: value.replace("_ms", "").upper(),
    default="p50_ms",
)

latency_df = latency_frame(ready, stat)
plot_latency = latency_df.dropna(subset=["Latency (ms)"])
if not plot_latency.empty:
    fig = px.bar(
        plot_latency,
        x="Workload",
        y="Latency (ms)",
        color="Database",
        barmode="group",
        color_discrete_map=COLORS,
    )
    st.plotly_chart(
        style_chart(fig, "milliseconds", "%{y:,.2f} ms<extra>%{fullData.name}</extra>"),
        use_container_width=True,
        config=PLOTLY_CONFIG,
    )
else:
    st.caption("No workload latencies yet.")

section("05", "Mixed read/write", "Sustained qps at 1 / 10 / 40 clients. Same 80/20 mix on every platform.")
if not mixed_df.empty:
    qps = mixed_df.dropna(subset=["Throughput (qps)"])
    fig = px.line(
        qps,
        x="Concurrency",
        y="Throughput (qps)",
        color="Database",
        markers=True,
        color_discrete_map=COLORS,
    )
    fig.update_traces(line=dict(width=2.2), marker=dict(size=6))
    st.plotly_chart(
        style_chart(fig, "queries / second", "<b>%{x} clients</b><br>%{y:,.2f} qps<extra>%{fullData.name}</extra>"),
        use_container_width=True,
        config=PLOTLY_CONFIG,
    )
    mixed_peak = float(mixed_df["Throughput (qps)"].max()) if pd.notna(mixed_df["Throughput (qps)"].max()) else 1.0
    mixed_config = {
        "Database": st.column_config.TextColumn("Database", width="medium"),
        "Concurrency": st.column_config.NumberColumn("Clients", format="%.0f"),
        "Throughput (qps)": st.column_config.ProgressColumn(
            "Throughput (qps)", min_value=0.0, max_value=mixed_peak, format="%.2f"
        ),
        "p50 (ms)": st.column_config.NumberColumn("p50 (ms)", format="%.2f"),
        "p95 (ms)": st.column_config.NumberColumn("p95 (ms)", format="%.2f"),
        "p99 (ms)": st.column_config.NumberColumn("p99 (ms)", format="%.2f"),
        "Success": st.column_config.ProgressColumn("Success", min_value=0.0, max_value=1.0, format="%.2f"),
        "Errors": st.column_config.NumberColumn("Errors", format="%.0f"),
    }
    st.dataframe(mixed_df, hide_index=True, use_container_width=True, column_config=mixed_config)
else:
    st.caption("No mixed-workload rows yet.")

waiting = [name for slug, name in PLATFORMS if slug not in ready_slugs]
if waiting:
    st.caption("Still waiting on: " + ", ".join(waiting) + ".")