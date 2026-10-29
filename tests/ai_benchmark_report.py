"""Summarize benchmark JSONL; exclude first observations from warm statistics."""

import argparse
import json
import math
import statistics
from collections import defaultdict

from ai_benchmark import fixtures


def latency(values):
    values = sorted(values)
    return {
        "median_ms": round(statistics.median(values), 1) if values else None,
        "p95_ms": round(values[math.ceil(len(values) * 0.95) - 1], 1)
        if values
        else None,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("results")
    args = parser.parse_args()
    sources = {case["id"]: case["source"] for case in fixtures()}
    groups = defaultdict(list)
    with open(args.results) as stream:
        for line in stream:
            row = json.loads(line)
            if row.get("sample", 0) > 0:
                groups[row["mode"], row["kind"]].append(row)
    for (mode, kind), rows in sorted(groups.items()):
        durations = [r["preview_ms"] for r in rows if r["preview_ms"] is not None]
        requests = [
            (q["finished"] - q["started"]) / 1e6
            for r in rows
            for q in r.get("requests", [])
            if "finished" in q
        ]
        failures = sorted({r["case"] for r in rows if not r["correct"]})
        print(
            json.dumps(
                {
                    "mode": mode,
                    "kind": kind,
                    "samples": len(rows),
                    "correct": sum(r["correct"] for r in rows),
                    "visible": sum(r["visible"] for r in rows),
                    "unchanged": sum(r["unchanged"] for r in rows),
                    "unrelated_prefix_changes": sum(
                        r["actual"].split("\n")[
                            : len(r.get("source", sources[r["case"]]).split("\n")) - 1
                        ]
                        != r.get("source", sources[r["case"]]).split("\n")[:-1]
                        for r in rows
                    ),
                    "preview": latency(durations),
                    "request": latency(requests),
                    "elapsed": latency([r["elapsed_ms"] for r in rows]),
                    "failures": failures,
                }
            )
        )


if __name__ == "__main__":
    main()
