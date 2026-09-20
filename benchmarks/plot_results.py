#!/usr/bin/env python3
"""Generate static benchmark charts from a measured results CSV."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


REQUIRED_COLUMNS = {"scenario", "failure_rate", "p95_ms", "p99_ms"}


def read_results(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError(f"results CSV is empty: {path}")
    columns = set(rows[0])
    missing = REQUIRED_COLUMNS - columns
    if missing:
        raise ValueError(f"results CSV is missing columns: {', '.join(sorted(missing))}")
    for row in rows:
        if not row.get("scenario"):
            raise ValueError("results CSV contains a row without a scenario")
        for column in ("failure_rate", "p95_ms", "p99_ms"):
            try:
                float(row[column])
            except (TypeError, ValueError) as exc:
                raise ValueError(f"results CSV has a non-numeric {column} value") from exc
    return rows


def generate_charts(rows: list[dict[str, str]], output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    scenarios = [row["scenario"] for row in rows]
    positions = list(range(len(scenarios)))
    p95 = [float(row["p95_ms"]) for row in rows]
    p99 = [float(row["p99_ms"]) for row in rows]
    failure_rate = [float(row["failure_rate"]) * 100 for row in rows]

    latency_path = output_dir / "latency_percentiles.png"
    figure, axis = plt.subplots(figsize=(11, 6))
    axis.plot(positions, p95, marker="o", linewidth=2, label="p95")
    axis.plot(positions, p99, marker="o", linewidth=2, label="p99")
    axis.set_title("Benchmark latency percentiles")
    axis.set_ylabel("Latency (ms)")
    axis.set_xticks(positions, scenarios, rotation=18, ha="right")
    axis.grid(axis="y", alpha=0.3)
    axis.legend()
    figure.tight_layout()
    figure.savefig(latency_path, dpi=150)
    plt.close(figure)

    failure_path = output_dir / "failure_rate.png"
    figure, axis = plt.subplots(figsize=(11, 6))
    bars = axis.bar(scenarios, failure_rate)
    axis.set_title("Benchmark failure rate")
    axis.set_ylabel("Failure rate (%)")
    axis.set_ylim(0, max(100, max(failure_rate) * 1.15))
    axis.tick_params(axis="x", rotation=18)
    for bar, value in zip(bars, failure_rate):
        axis.annotate(f"{value:.2f}%", (bar.get_x() + bar.get_width() / 2, value), ha="center", va="bottom")
    axis.grid(axis="y", alpha=0.3)
    figure.tight_layout()
    figure.savefig(failure_path, dpi=150)
    plt.close(figure)
    return latency_path, failure_path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=Path("benchmarks/results.csv"))
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    output_dir = args.output_dir or args.input.parent
    rows = read_results(args.input)
    outputs = generate_charts(rows, output_dir)
    for output in outputs:
        print(f"generated {output} ({output.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
