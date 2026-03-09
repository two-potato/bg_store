#!/usr/bin/env python3
import csv
import statistics
import sys
from pathlib import Path


def parse_session(prefix: Path) -> dict:
    stats_file = prefix.with_name(prefix.name + "_stats.csv")
    hist_file = prefix.with_name(prefix.name + "_stats_history.csv")
    if not stats_file.exists():
        return {}

    total = {}
    with stats_file.open("r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for row in rows:
        if row.get("Type") == "" and row.get("Name") == "Aggregated":
            total = row
            break
    if not total:
        return {}

    rps_vals = []
    with hist_file.open("r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                rps_vals.append(float(row.get("Total RPS", "0") or "0"))
            except ValueError:
                continue

    reqs = int(float(total.get("Request Count", "0") or "0"))
    fails = int(float(total.get("Failure Count", "0") or "0"))
    fail_pct = (fails / reqs * 100) if reqs else 0.0
    p95 = float(total.get("95%", "0") or "0")
    p99 = float(total.get("99%", "0") or "0")
    avg = float(total.get("Average Response Time", "0") or "0")
    max_rt = float(total.get("Max Response Time", "0") or "0")

    return {
        "name": prefix.name,
        "requests": reqs,
        "failures": fails,
        "fail_pct": fail_pct,
        "avg_rt_ms": avg,
        "p95_ms": p95,
        "p99_ms": p99,
        "max_rt_ms": max_rt,
        "rps_avg": statistics.mean(rps_vals) if rps_vals else 0.0,
        "rps_peak": max(rps_vals) if rps_vals else 0.0,
    }


def format_report(run_dir: Path, sessions: list[dict]) -> str:
    total_reqs = sum(s["requests"] for s in sessions)
    total_fails = sum(s["failures"] for s in sessions)
    total_fail_pct = (total_fails / total_reqs * 100) if total_reqs else 0.0
    peak_rps = max((s["rps_peak"] for s in sessions), default=0.0)
    worst_p95 = max((s["p95_ms"] for s in sessions), default=0.0)

    lines = [
        "📊 <b>Нагрузочное тестирование (staircase, multi-session)</b>",
        f"Папка отчётов: <code>{run_dir}</code>",
        "",
        f"Итого запросов: <b>{total_reqs}</b>",
        f"Итого ошибок: <b>{total_fails}</b> ({total_fail_pct:.2f}%)",
        f"Пиковый RPS: <b>{peak_rps:.2f}</b>",
        f"Худший p95: <b>{worst_p95:.0f} ms</b>",
        "",
        "<b>Сессии:</b>",
    ]
    for s in sessions:
        lines.append(
            f"• <b>{s['name']}</b>: req={s['requests']}, err={s['failures']} ({s['fail_pct']:.2f}%), "
            f"avg={s['avg_rt_ms']:.0f}ms, p95={s['p95_ms']:.0f}ms, p99={s['p99_ms']:.0f}ms, "
            f"RPS avg/peak={s['rps_avg']:.2f}/{s['rps_peak']:.2f}"
        )
    return "\n".join(lines)


def main():
    if len(sys.argv) != 2:
        print("Usage: summarize_locust_runs.py <run_dir>")
        sys.exit(1)
    run_dir = Path(sys.argv[1]).resolve()
    if not run_dir.exists():
        print(f"Run dir not found: {run_dir}")
        sys.exit(2)

    session_prefixes = sorted(
        p.with_name(p.name.removesuffix("_stats.csv")) for p in run_dir.glob("s*_stats.csv")
    )

    sessions = []
    for p in session_prefixes:
        s = parse_session(p)
        if s:
            sessions.append(s)

    if not sessions:
        print("No session data found")
        sys.exit(3)

    report = format_report(run_dir, sessions)
    out = run_dir / "summary_report.txt"
    out.write_text(report, encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
