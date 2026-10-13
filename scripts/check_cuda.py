"""Check the project environment and execute a small CUDA operation."""

import json
import sys
from pathlib import Path

import torch


def main():
    root = Path(__file__).resolve().parents[1]
    if Path(sys.prefix).resolve() != (root / ".venv").resolve():
        raise SystemExit("Run with .\\.venv\\Scripts\\python.exe scripts/check_cuda.py")
    if not torch.cuda.is_available():
        raise SystemExit("CUDA is unavailable in this environment.")

    device = torch.device("cuda:0")
    with torch.inference_mode():
        values = torch.arange(1024, device=device, dtype=torch.float32)
        actual = (values * 2).sum().item()
        expected = 1023 * 1024
        if actual != expected:
            raise SystemExit(f"CUDA computation failed: {actual} != {expected}")
        matrix = torch.eye(256, device=device)
        if not torch.equal(matrix @ matrix, matrix):
            raise SystemExit("CUDA matrix multiplication failed.")
        torch.cuda.synchronize()

    props = torch.cuda.get_device_properties(device)
    print(json.dumps({
        "python": sys.version.split()[0],
        "environment": sys.prefix,
        "torch": torch.__version__,
        "cuda_runtime": torch.version.cuda,
        "gpu": props.name,
        "vram_gib": round(props.total_memory / 1024**3, 2),
        "compute_capability": f"{props.major}.{props.minor}",
        "cuda_computation": "passed",
    }, indent=2))


if __name__ == "__main__":
    main()
