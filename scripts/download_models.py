"""SeeGuide Model Provisioning and Verification Script
Downloads pinned OpenCV Zoo ONNX models and verifies SHA256 cryptographic checksums:
1. YOLOX-nano / S (object_detection_yolox_2022nov.onnx)
2. Text Detection DB (text_detection_DB_IC15_resnet18_2021sep.onnx)
3. Text Recognition CRNN (text_recognition_CRNN_EN_2021sep.onnx)
4. YuNet Face Detector (face_detection_yunet_2023mar.onnx)
Plus CRNN English character dictionary (charset_36_EN.txt).
"""

import hashlib
from pathlib import Path
import sys
import urllib.request

REPO_ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = REPO_ROOT / "models"

# Pinned commit hashes / models metadata
OPENCV_ZOO_COMMIT = "6a66e0d6e47a693e6d0dd01bbb18e920f3fbae75"

MODELS_SPEC = {
    "yolox_nano.onnx": {
        "url": "https://huggingface.co/opencv/object_detection_yolox/resolve/main/object_detection_yolox_2022nov.onnx",
        "sha256": "c5c2d13e59ae883e6af3b45daea64af4833a4951c92d116ec270d9ddbe998063",
        "desc": "OpenCV Zoo YOLOX Object Detector (ONNX)",
    },
    "text_detection_DB.onnx": {
        "url": f"https://github.com/opencv/opencv_zoo/raw/{OPENCV_ZOO_COMMIT}/models/text_detection_db/text_detection_DB_IC15_resnet18_2021sep.onnx",
        "sha256": "62fce3a058ac519952062fbd2cf45bae661130ce753d2a0fc918f4776ba3a02a",
        "desc": "OpenCV Zoo Text Detection DB-ResNet18 (ONNX)",
    },
    "text_recognition_CRNN.onnx": {
        "url": "https://huggingface.co/opencv/text_recognition_crnn/resolve/main/text_recognition_CRNN_EN_2021sep.onnx",
        "sha256": "a84b1f6e11a65c2d733cb0cc1f014aae3f99051e3f11447dc282faa678eee544",
        "desc": "OpenCV Zoo Text Recognition CRNN-EN (ONNX)",
    },
    "face_detection_yunet.onnx": {
        "url": "https://huggingface.co/opencv/face_detection_yunet/resolve/main/face_detection_yunet_2023mar.onnx",
        "sha256": "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4",
        "desc": "OpenCV Zoo YuNet Face Detector (ONNX)",
    },
}

CHARSET_EN = "0\n1\n2\n3\n4\n5\n6\n7\n8\n9\na\nb\nc\nd\ne\nf\ng\nh\ni\nj\nk\nl\nm\nn\no\np\nq\nr\ns\nt\nu\nv\nw\nx\ny\nz\n"


def compute_sha256(file_path: Path) -> str:
    """Computes SHA256 hash of a file in 64KB chunks."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def download_and_verify(target_dir: Path = MODELS_DIR) -> bool:
    target_dir.mkdir(parents=True, exist_ok=True)
    print("=" * 70)
    print("SeeGuide OpenCV Zoo Model Provisioner & Checksum Verifier")
    print(f"Target Directory: {target_dir}")
    print(f"Pinned OpenCV Zoo Commit: {OPENCV_ZOO_COMMIT}")
    print("=" * 70)

    # Write charset file if not present
    charset_path = target_dir / "charset_36_EN.txt"
    if not charset_path.exists():
        charset_path.write_text(CHARSET_EN, encoding="utf-8")
        print(f"[OK] Wrote CRNN English vocabulary to {charset_path.name}")

    all_verified = True

    for filename, spec in MODELS_SPEC.items():
        file_path = target_dir / filename
        expected_hash = spec["sha256"]
        desc = spec["desc"]

        # Check if already present and valid
        if file_path.exists():
            current_hash = compute_sha256(file_path)
            if current_hash == expected_hash:
                print(f"[EXISTS & VERIFIED] {filename:<28} - {desc}")
                continue
            else:
                print(f"[WARN] Checksum mismatch for {filename}. Re-downloading...")
                file_path.unlink()

        # Download file
        print(f"[DOWNLOADING] {filename} from {spec['url']}...")
        try:
            req = urllib.request.Request(spec["url"], headers={"User-Agent": "SeeGuide-Downloader/1.0"})
            with urllib.request.urlopen(req, timeout=60) as resp, open(file_path, "wb") as out_f:
                while chunk := resp.read(65536):
                    out_f.write(chunk)
            
            # Verify downloaded hash
            actual_hash = compute_sha256(file_path)
            if actual_hash == expected_hash:
                print(f"[VERIFIED] {filename:<28} SHA256: {actual_hash[:16]}... matches expected.")
            else:
                print(f"[FAILED] {filename} SHA256 mismatch!")
                print(f"  Expected: {expected_hash}")
                print(f"  Actual:   {actual_hash}")
                file_path.unlink(missing_ok=True)
                all_verified = False
        except Exception as e:
            print(f"[ERROR] Failed to download {filename}: {e}")
            all_verified = False

    print("=" * 70)
    if all_verified:
        print("RESULT: ALL 4 OPENCV ZOO ONNX MODELS PROVISIONED AND VERIFIED.")
        return True
    else:
        print("RESULT: MODEL PROVISIONING ENCOUNTERED ERRORS.")
        return False


if __name__ == "__main__":
    success = download_and_verify()
    sys.exit(0 if success else 1)
