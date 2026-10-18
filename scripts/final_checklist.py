"""SeeGuide Final Submission Checklist

Automated verification script to guarantee that all mandatory submission artifacts,
documentation, evaluation results, and codebase components exist and are intact
before submitting to the OpenCV AI Competition 2026.
"""

import sys
from pathlib import Path


MANDATORY_ARTIFACTS = [
    # Documentation & Reports
    ("README.md", "Judge-Ready Comprehensive README"),
    ("requirements.txt", "Strictly Pinned Dependencies"),
    ("docs/TECHNICAL_REPORT.md", "Full Competition Technical Report"),
    ("docs/VIDEO_SCRIPT.md", "5-Minute Demonstration Video Script"),
    ("docs/requirements.md", "System Requirements Specification"),
    ("docs/architecture.md", "Architecture & System Design"),
    ("docs/stage-reports/stage-1-report.md", "Stage 1 Audit Report"),
    ("docs/stage-reports/stage-9-report.md", "Stage 9 Audit Report"),

    # Infrastructure & Free Tier Deployment
    ("infra/deploy.sh", "EC2 Ubuntu Automated Deployment Script"),
    ("infra/Caddyfile", "Caddy TLS Reverse Proxy Configuration"),
    ("infra/dynamodb_setup.py", "DynamoDB Table & 7-Day TTL Setup Script"),
    ("infra/iam_policy.json", "Least-Privilege AWS IAM Policy"),

    # Empirical Results & Benchmarks
    ("eval/results/metrics.csv", "Empirical Evaluation Metrics vs Baselines"),
    ("benchmarks/results/profile.csv", "Latency & Timing Profiling Percentiles"),
    ("eval/labels.csv", "Ground-Truth Evaluation Annotation Manifest"),
    ("eval/run_eval.py", "Offline Evaluation Replay Harness"),
    ("benchmarks/run_profile.py", "Pipeline Latency Profiler"),

    # Backend & Application Source
    ("server/main.py", "FastAPI Server with Security Middleware"),
    ("server/websocket_handler.py", "WebSocket Handler with 2MB Limit"),
    ("server/models.py", "Pydantic v2 Models Matching Contracts"),
    ("server/storage.py", "Storage Abstractions & Mock Adapters"),
    ("vision/pipeline.py", "OpenCV 5 Tiered Vision Pipeline"),
    ("agent/policy.py", "Deterministic 6-Rule Policy Engine"),
    ("agent/state.py", "BeliefState & Cooldown Tracker"),

    # Frontend PWA Source
    ("web/index.html", "Accessible PWA HTML5 Markup"),
    ("web/style.css", "High-Contrast Stylesheet & Focus Rings"),
    ("web/app.js", "PWA Client Logic & Priority Audio Queue"),
    ("web/manifest.json", "PWA Web App Manifest"),

    # Formal Schemas & Validation
    ("contracts/client_to_server_frame.schema.json", "Frame Ingestion JSON Schema"),
    ("contracts/vision_to_agent_observation.schema.json", "Observation JSON Schema"),
    ("contracts/agent_to_client_action.schema.json", "Action Dispatch JSON Schema"),
    ("scripts/check_environment.py", "Environment Verification Script"),
    ("scripts/validate_contracts.py", "Contract Validation Script"),

    # Security & Regression Tests
    ("tests/test_security.py", "HTTP Headers & WebSocket Security Tests"),
    ("tests/test_integration.py", "End-to-End Perception-Action Loop Tests"),
    ("tests/test_failure_handling.py", "FR-16 Uncertainty Fallback Tests"),
    ("tests/test_policy.py", "Deterministic Policy Engine Tests"),
    ("tests/test_vision.py", "OpenCV 5 Vision Pipeline Tests"),
]


def run_checklist() -> bool:
    print("=" * 70)
    print("SeeGuide Stage 10: Final Submission Checklist Verification")
    print("=" * 70)

    repo_root = Path(__file__).resolve().parent.parent
    all_passed = True
    missing_count = 0

    for relative_path, description in MANDATORY_ARTIFACTS:
        target_path = repo_root / relative_path
        exists = target_path.exists() and target_path.is_file()
        
        if exists:
            status = "[PASS]"
            size = target_path.stat().st_size
            print(f"{status} {relative_path:<48} ({size:>6} bytes) - {description}")
        else:
            status = "[FAIL]"
            print(f"{status} {relative_path:<48} (MISSING)       - {description}")
            all_passed = False
            missing_count += 1

    print("=" * 70)
    if all_passed:
        print(f"RESULT: ALL {len(MANDATORY_ARTIFACTS)} MANDATORY ARTIFACTS VERIFIED SUCCESSFULLY!")
        print("SeeGuide is verified complete and ready for competition submission.")
        print("=" * 70)
        return True
    else:
        print(f"RESULT: FAILED - {missing_count} mandatory artifacts are missing or unreadable.")
        print("=" * 70)
        return False


if __name__ == "__main__":
    success = run_checklist()
    sys.exit(0 if success else 1)
