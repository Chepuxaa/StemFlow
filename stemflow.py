"""Source and frozen entry point. GUI stays light; inference runs in its worker."""

import sys
from pathlib import Path


def main():
    headless = any(flag in sys.argv for flag in ('--worker', '--probe-device', '--download-model', '--self-test')) or (getattr(sys, 'frozen', False) and Path(sys.executable).stem.endswith('-worker'))
    if headless:
        from worker_stdio import restore_worker_stdio
        restore_worker_stdio()
    if '--download-model' in sys.argv:
        sys.argv.remove('--download-model')
        from scripts.download_model import main as download
        download()
    elif '--probe-device' in sys.argv:
        import json
        from cuda_runtime import probe_device
        print(json.dumps(probe_device()))
    elif '--worker' in sys.argv or '--self-test' in sys.argv or (getattr(sys, 'frozen', False) and Path(sys.executable).stem.endswith('-worker')):
        from separate import main as worker
        worker()
    else:
        from desktop import main as gui
        gui()


if __name__ == '__main__':
    from multiprocessing import freeze_support
    freeze_support()
    main()
