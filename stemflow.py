"""Source and frozen entry point. GUI stays light; inference runs in its worker."""

import sys
from pathlib import Path


def main():
    if '--download-model' in sys.argv:
        sys.argv.remove('--download-model')
        from scripts.download_model import main as download
        download()
    elif '--probe-device' in sys.argv:
        import json
        import torch
        available = torch.cuda.is_available()
        if available:
            probe = torch.ones(1, device='cuda') + 1
            torch.cuda.synchronize()
        print(json.dumps({'cuda_available': available,
                         'name': torch.cuda.get_device_name(0).removeprefix('NVIDIA GeForce ') if available else 'CPU',
                         'memory_gib': round(torch.cuda.get_device_properties(0).total_memory / 1024**3, 1) if available else None}))
    elif '--worker' in sys.argv or (getattr(sys, 'frozen', False) and Path(sys.executable).stem.endswith('-worker')):
        from separate import main as worker
        worker()
    else:
        from desktop import main as gui
        gui()


if __name__ == '__main__':
    from multiprocessing import freeze_support
    freeze_support()
    main()
