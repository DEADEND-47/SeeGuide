"""Unit and Integration Tests for SeeGuide Performance Profiler
Verifies latency micro-benchmarks, percentiles calculation, and profile.csv generation.
"""

import csv
from pathlib import Path
import pytest

from benchmarks.run_profile import run_profiler


def test_profiler_generates_valid_profile_csv(tmp_path):
    """Runs latency profiler on synthetic frames and verifies profile.csv outputs."""
    out_csv = tmp_path / "profile.csv"

    generated_path = run_profiler(
        num_frames=10,
        output_path=out_csv,
        instance_type="test-runner",
    )

    assert generated_path.exists()
    assert generated_path.name == "profile.csv"

    with open(generated_path, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    assert len(rows) >= 6
    stages = [r["stage"] for r in rows]
    expected_stages = ["decode", "fast_tier", "detector", "ocr", "agent_decide", "total_cycle"]
    for s in expected_stages:
        assert s in stages

    for r in rows:
        assert float(r["p50_ms"]) >= 0.0
        assert float(r["p95_ms"]) >= float(r["p50_ms"]) or abs(float(r["p95_ms"]) - float(r["p50_ms"])) < 0.01
        assert float(r["min_ms"]) <= float(r["max_ms"])
        assert r["instance_type"] == "test-runner"
        assert len(r["python_version"]) > 0
        assert len(r["opencv_version"]) > 0
