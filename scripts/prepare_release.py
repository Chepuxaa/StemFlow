"""Add first-run instructions and available license texts to the Windows bundle."""

from importlib import metadata
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]


def collect_licenses(license_root):
    license_root = Path(license_root)
    license_root.mkdir(parents=True, exist_ok=True)
    ffmpeg_root = license_root / 'FFmpeg'
    ffmpeg_root.mkdir(parents=True, exist_ok=True)
    for source in (ROOT / 'packaging/licenses').iterdir():
        if source.is_file():
            shutil.copyfile(source, ffmpeg_root / source.name)
        elif source.is_dir():
            shutil.copytree(source, license_root / source.name, dirs_exist_ok=True)
    packages = [line.split('==')[0] for line in (ROOT / 'requirements/app.lock.txt').read_text().splitlines() if '==' in line]
    packages.append('pyinstaller')
    count = 0
    for name in packages:
        distribution = metadata.distribution(name)
        for relative in distribution.files or []:
            path = Path(relative)
            if not any(token in path.name.upper() for token in ('LICENSE', 'LICENCE', 'COPYING', 'NOTICE')):
                continue
            source = Path(distribution.locate_file(relative))
            if not source.is_file():
                continue
            safe_parts = [part for part in path.parts if part not in ('..', '.', '/')]
            target = license_root / name / Path(*safe_parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            count += 1
    python_license = Path(sys.base_prefix) / 'LICENSE.txt'
    if python_license.is_file():
        (license_root / 'Python').mkdir(parents=True, exist_ok=True)
        shutil.copyfile(python_license, license_root / 'Python/LICENSE.txt')
    return count


def main():
    if (ROOT / 'dist/StemFlow.exe').is_file():
        print('Single-file build ready: dist/StemFlow.exe. License texts are embedded.')
        return
    bundle = ROOT / 'dist/StemFlow'
    if not (bundle / 'StemFlow.exe').is_file() or not (bundle / 'StemFlow-worker.exe').is_file():
        raise SystemExit('Build the Windows app first.')
    for name in ('Download-model.cmd', 'READ-ME-FIRST.txt'):
        shutil.copyfile(ROOT / 'packaging' / name, bundle / name)
    shutil.copyfile(ROOT / 'LICENSE', bundle / 'LICENSE')
    shutil.copyfile(ROOT / 'THIRD_PARTY_NOTICES.md', bundle / 'THIRD_PARTY_NOTICES.md')
    count = collect_licenses(bundle / 'THIRD_PARTY_LICENSES')
    print(f'Prepared bundle; copied {count} dependency license files.')


if __name__ == '__main__':
    main()
