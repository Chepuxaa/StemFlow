"""Create an uploadable source ZIP without models, audio, environment or cache."""

import argparse
from pathlib import Path
import sys
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app_paths import DATA_DIR
from scripts.check_repository import ROOT, source_files, main as check


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination', type=Path, default=DATA_DIR / 'StemFlow-source.zip')
    args = parser.parse_args()
    check()
    if args.destination.exists():
        raise SystemExit(f'Archive already exists: {args.destination}')
    args.destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.destination, 'x', zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(set(source_files())):
            archive.write(path, 'StemFlow/' + path.relative_to(ROOT).as_posix())
    print(f'Source archive: {args.destination}')


if __name__ == '__main__':
    main()
