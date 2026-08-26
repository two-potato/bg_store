#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from pathlib import Path


def _read_aggregated_row(stats_file: Path) -> dict[str, str] | None:
    with stats_file.open("r", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row.get("Type") == "" and row.get("Name") == "Aggregated":
                return row
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate locust run against p95/error budgets.")
    parser.add_argument("--run-dir", required=True, help="Path to locust run directory")
    parser.add_argument("--max-p95-ms", type=float, default=1200.0)
    parser.add_argument("--max-failure-rate", type=float, default=0.01)
    args = parser.parse_args()

    run_dir = Path(args.run_dir).resolve()
    stats_files = sorted(run_dir.glob("s*_stats.csv"))
    if not stats_files:
        print(f"No stats files found in {run_dir}")
        return 2

    worst_p95 = 0.0
    worst_failure_rate = 0.0
    for stats_file in stats_files:
        aggregated = _read_aggregated_row(stats_file)
        if not aggregated:
            continue
        request_count = float(aggregated.get("Request Count", "0") or "0")
        failure_count = float(aggregated.get("Failure Count", "0") or "0")
        p95 = float(aggregated.get("95%", "0") or "0")
        failure_rate = (failure_count / request_count) if request_count else 0.0
        worst_p95 = max(worst_p95, p95)
        worst_failure_rate = max(worst_failure_rate, failure_rate)

    print(f"worst_p95_ms={worst_p95:.2f}")
    print(f"worst_failure_rate={worst_failure_rate:.4f}")
    if worst_p95 > args.max_p95_ms:
        print(f"p95 budget violated: {worst_p95:.2f} > {args.max_p95_ms:.2f}")
        return 1
    if worst_failure_rate > args.max_failure_rate:
        print(f"failure-rate budget violated: {worst_failure_rate:.4f} > {args.max_failure_rate:.4f}")
        return 1
    print("load budget check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
