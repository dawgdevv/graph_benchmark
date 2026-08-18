from statistics import mean,stdev

import numpy as np


def summarize_latencies(latencies_ms: list[float])-> dict[str,float]
    if not latencies_ms:
        raise ValueError("latencies_ms cannot be empty")

    result ={
        "count": len(latencies_ms),
        "min_ms": float(min(latencies_ms)),
        "mean_ms": float(mean(latencies_ms)),
        "p50_ms": float(np.percentile(latencies_ms,50)),
        "p95_ms": float(np.percentile(latencies_ms,95)),
        "max_ms":float(max(latencies_ms)),
        "stddev_ms":0.0,
    }

    if len(latencies_ms)>1:
        result["stddev_ms"]=float(stdev(latencies_ms))
    return result