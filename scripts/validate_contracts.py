#!/usr/bin/env python3
"""
SeeGuide Stage 1 Contract Validator
Validates example JSON payloads against their JSON Schema specifications
using only the Python standard library (no external dependencies required).
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple


def check_type(val: Any, expected_type: Any) -> bool:
    """Check value type against JSON schema type specification."""
    if isinstance(expected_type, list):
        return any(check_type(val, t) for t in expected_type)
    
    if expected_type == "string":
        return isinstance(val, str)
    elif expected_type == "number":
        return isinstance(val, (int, float)) and not isinstance(val, bool)
    elif expected_type == "integer":
        return isinstance(val, int) and not isinstance(val, bool)
    elif expected_type == "boolean":
        return isinstance(val, bool)
    elif expected_type == "object":
        return isinstance(val, dict)
    elif expected_type == "array":
        return isinstance(val, list)
    elif expected_type == "null":
        return val is None
    return False


def validate_object(data: Dict[str, Any], schema: Dict[str, Any], path: str = "root") -> List[str]:
    """Validate a dictionary object against a schema definition."""
    errors = []

    if not isinstance(data, dict):
        return [f"'{path}' must be an object (dictionary), got {type(data).__name__}"]

    required_fields = schema.get("required", [])
    for field in required_fields:
        if field not in data:
            errors.append(f"Missing required field: '{path}.{field}'")

    properties = schema.get("properties", {})
    additional_allowed = schema.get("additionalProperties", True)

    if not additional_allowed:
        for key in data:
            if key not in properties:
                errors.append(f"Unexpected extra field not permitted by schema: '{path}.{key}'")

    for key, val in data.items():
        if key not in properties:
            continue
        prop_schema = properties[key]
        field_path = f"{path}.{key}"

        # Type check
        expected_type = prop_schema.get("type")
        if expected_type is not None:
            if not check_type(val, expected_type):
                errors.append(
                    f"Field '{field_path}' expected type '{expected_type}', got {type(val).__name__} (value: {val!r})"
                )
                continue

        # Const check
        if "const" in prop_schema and val != prop_schema["const"]:
            errors.append(f"Field '{field_path}' must equal const {prop_schema['const']!r}, got {val!r}")

        # Enum check
        if "enum" in prop_schema and val not in prop_schema["enum"]:
            errors.append(f"Field '{field_path}' value {val!r} not in permitted enum {prop_schema['enum']}")

        # Nested Object validation
        if isinstance(val, dict) and prop_schema.get("type") == "object":
            errors.extend(validate_object(val, prop_schema, path=field_path))

        # Array validation
        if isinstance(val, list) and prop_schema.get("type") == "array":
            item_schema = prop_schema.get("items")
            if item_schema and item_schema.get("type") == "object":
                for idx, item in enumerate(val):
                    errors.extend(validate_object(item, item_schema, path=f"{field_path}[{idx}]"))
            min_items = prop_schema.get("minItems")
            if min_items is not None and len(val) < min_items:
                errors.append(f"Array '{field_path}' requires minimum {min_items} items, got {len(val)}")
            max_items = prop_schema.get("maxItems")
            if max_items is not None and len(val) > max_items:
                errors.append(f"Array '{field_path}' permits maximum {max_items} items, got {len(val)}")

    return errors


def run_contract_validations(base_dir: Path) -> Tuple[int, int]:
    """Execute validations for all defined contract-example pairs."""
    contract_pairs = [
        (
            "Client-to-Server Frame Message",
            base_dir / "contracts" / "client_to_server_frame.schema.json",
            base_dir / "examples" / "frame_message.example.json",
        ),
        (
            "Vision-to-Agent Observation",
            base_dir / "contracts" / "vision_to_agent_observation.schema.json",
            base_dir / "examples" / "observation.example.json",
        ),
        (
            "Agent-to-Client Action Message",
            base_dir / "contracts" / "agent_to_client_action.schema.json",
            base_dir / "examples" / "action.example.json",
        ),
    ]

    total_passed = 0
    total_failed = 0

    print("====================================================================")
    print("SeeGuide Stage 1 Contract Validation Suite")
    print("====================================================================")

    for name, schema_path, example_path in contract_pairs:
        print(f"\n[Contract] {name}")
        print(f"  Schema:  {schema_path.relative_to(base_dir)}")
        print(f"  Example: {example_path.relative_to(base_dir)}")

        # Check file existence
        if not schema_path.exists():
            print(f"  [FAIL] Schema file missing: {schema_path}")
            total_failed += 1
            continue
        if not example_path.exists():
            print(f"  [FAIL] Example file missing: {example_path}")
            total_failed += 1
            continue

        # Load JSON files
        try:
            with open(schema_path, "r", encoding="utf-8") as f:
                schema = json.load(f)
        except Exception as e:
            print(f"  [FAIL] Error parsing schema JSON: {e}")
            total_failed += 1
            continue

        try:
            with open(example_path, "r", encoding="utf-8") as f:
                example = json.load(f)
        except Exception as e:
            print(f"  [FAIL] Error parsing example JSON: {e}")
            total_failed += 1
            continue

        # Validate
        errors = validate_object(example, schema)
        if errors:
            print("  [FAIL] Validation errors encountered:")
            for err in errors:
                print(f"    - {err}")
            total_failed += 1
        else:
            print("  [PASS] All required fields, types, and constraints verified successfully.")
            total_passed += 1

    print("\n====================================================================")
    print(f"Summary: {total_passed} passed, {total_failed} failed.")
    print("====================================================================")

    return total_passed, total_failed


def main() -> int:
    script_dir = Path(__file__).resolve().parent
    base_dir = script_dir.parent

    passed, failed = run_contract_validations(base_dir)
    if failed > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
