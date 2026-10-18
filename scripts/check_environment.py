#!/usr/bin/env python3
"""
SeeGuide Environment Verification Script
Validates Python runtime version (>=3.11), OpenCV 5.x headless presence,
FastAPI, Pydantic, WebSockets, and core development dependencies.
"""

import sys


def main() -> int:
    print("====================================================================")
    print("SeeGuide Stage 2 Environment Verification")
    print("====================================================================")

    failures = []

    # 1. Verify Python Version >= 3.11
    py_ver = sys.version_info
    py_ver_str = f"{py_ver.major}.{py_ver.minor}.{py_ver.micro}"
    print(f"[*] Checking Python runtime: detected {py_ver_str}")
    if (py_ver.major, py_ver.minor) < (3, 11):
        err = f"Python version must be >= 3.11 (detected {py_ver_str})"
        print(f"    [FAIL] {err}")
        failures.append(err)
    else:
        print(f"    [PASS] Python version {py_ver_str} satisfies requirement (>= 3.11).")

    # 2. Verify OpenCV 5.x installation
    print("[*] Checking OpenCV installation...")
    try:
        import cv2
        cv_version = getattr(cv2, "__version__", "unknown")
        print(f"    Detected cv2.__version__ = {cv_version}")
        if not cv_version.startswith("5."):
            err = f"OpenCV must be version 5.x for OpenCV AI Competition 2026. Found: {cv_version}"
            print(f"    [FAIL] {err}")
            failures.append(err)
        else:
            print(f"    [PASS] OpenCV 5.x verified ({cv_version}).")
    except ImportError as e:
        err = f"Failed to import cv2: {e}. Please ensure opencv-python-headless==5.0.0.93 is installed."
        print(f"    [FAIL] {err}")
        failures.append(err)

    # 3. Verify FastAPI
    print("[*] Checking FastAPI installation...")
    try:
        import fastapi
        fastapi_ver = getattr(fastapi, "__version__", "unknown")
        print(f"    [PASS] FastAPI verified ({fastapi_ver}).")
    except ImportError as e:
        err = f"Failed to import fastapi: {e}"
        print(f"    [FAIL] {err}")
        failures.append(err)

    # 4. Verify Pydantic
    print("[*] Checking Pydantic installation...")
    try:
        import pydantic
        pydantic_ver = getattr(pydantic, "__version__", "unknown")
        print(f"    [PASS] Pydantic verified ({pydantic_ver}).")
    except ImportError as e:
        err = f"Failed to import pydantic: {e}"
        print(f"    [FAIL] {err}")
        failures.append(err)

    # 5. Verify WebSockets
    print("[*] Checking WebSockets installation...")
    try:
        import websockets
        ws_ver = getattr(websockets, "__version__", "unknown")
        print(f"    [PASS] WebSockets verified ({ws_ver}).")
    except ImportError as e:
        err = f"Failed to import websockets: {e}"
        print(f"    [FAIL] {err}")
        failures.append(err)

    # 6. Optional runtime checks (boto3, uvicorn, pytest)
    for pkg_name in ["uvicorn", "boto3", "pytest", "dotenv"]:
        try:
            mod = __import__(pkg_name)
            ver = getattr(mod, "__version__", "installed")
            print(f"    [INFO] {pkg_name}: {ver}")
        except ImportError:
            print(f"    [INFO] {pkg_name}: not installed or optional at this stage")

    print("====================================================================")
    if failures:
        print(f"Environment Verification FAILED with {len(failures)} error(s):")
        for f in failures:
            print(f"  - {f}")
        print("====================================================================")
        return 1

    print("All core environment requirements VERIFIED successfully!")
    print("====================================================================")
    return 0


if __name__ == "__main__":
    sys.exit(main())
