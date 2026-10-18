"""Unit and Integration Tests for SeeGuide Evaluation Replay Runner
Verifies ground truth replay execution, baseline comparisons, and metrics.csv generation.
"""

import csv
from pathlib import Path
import pytest

from eval.run_eval import run_evaluation


def test_run_eval_generates_valid_metrics_csv(tmp_path):
    """Executes evaluation harness with dummy labels and verifies metrics.csv outputs."""
    # Create temporary labels file
    test_labels = tmp_path / "test_labels.csv"
    test_labels.write_text(
        "clip_id,expected_action,event_time_s,mode,notes\n"
        "clip_test_looming,speak,2.0,walk,Looming test obstacle\n"
        "clip_test_clear,stay_silent,0.0,walk,Clear test path\n"
        "clip_test_sign,speak,1.5,read,Door sign test\n",
        encoding="utf-8",
    )

    results_dir = tmp_path / "results"

    # Run evaluation
    metrics_file = run_evaluation(
        labels_path=test_labels,
        output_dir=results_dir,
        clips_dir=None,
    )

    assert metrics_file.exists()
    assert metrics_file.name == "metrics.csv"

    # Verify rows and headers
    with open(metrics_file, "r", encoding="utf-8") as f:
        reader = list(csv.DictReader(f))

    assert len(reader) == 3
    system_names = [row["system"] for row in reader]
    assert "SeeGuide" in system_names
    assert "B0" in system_names
    assert "B1" in system_names

    # Check headers
    expected_headers = {
        "system",
        "hazard_recall",
        "time_to_warn_ms",
        "false_alarms_per_min",
        "speech_reduction_pct",
        "ocr_success_rate",
        "silence_correctness",
    }
    assert expected_headers.issubset(set(reader[0].keys()))

    # Verify metric value validity
    for row in reader:
        assert 0.0 <= float(row["hazard_recall"]) <= 1.0
        assert float(row["time_to_warn_ms"]) >= 0.0
        assert float(row["false_alarms_per_min"]) >= 0.0
        assert 0.0 <= float(row["speech_reduction_pct"]) <= 100.0
        assert 0.0 <= float(row["ocr_success_rate"]) <= 1.0
        assert 0.0 <= float(row["silence_correctness"]) <= 1.0
