"""Test suite for contract schemas: Validates that frame, observation, and action example payloads conform to their schemas."""

from pathlib import Path
from scripts.validate_contracts import run_contract_validations


def test_contracts_valid():
    """Verify all Stage 1 contract schemas and example payloads validate successfully."""
    base_dir = Path(__file__).resolve().parent.parent
    passed, failed = run_contract_validations(base_dir)
    assert failed == 0
    assert passed == 3
