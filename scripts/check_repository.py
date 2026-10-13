"""Fast source checks; no CUDA, model weights or external dependencies required."""

import ast
import hashlib
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def source_files():
    roots = [ROOT, ROOT / 'scripts', ROOT / 'ui', ROOT / 'config', ROOT / 'packaging', ROOT / '.github', ROOT / 'docs', ROOT / 'vendor']
    for directory in roots:
        if not directory.exists():
            continue
        files = directory.glob('*') if directory == ROOT else directory.rglob('*')
        for path in files:
            if not path.is_file() or '__pycache__' in path.parts or path.suffix in ('.pyc', '.pyo'):
                continue
            if directory == ROOT and path.suffix not in ('.py', '.md', '.cmd') and path.name not in ('.gitignore', '.gitattributes', '.editorconfig', 'LICENSE'):
                continue
            if not path.resolve().is_relative_to(ROOT.resolve()):
                raise ValueError(f'Source file points outside repository: {path}')
            yield path
    for path in (ROOT / 'requirements').glob('*.txt'):
        if not path.name.startswith('benchmarks'):
            yield path


def main():
    for path in source_files():
        if path.suffix in ('.py', '.spec'):
            ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
        if path.suffix == '.svg':
            ET.parse(path)
    manifest = json.loads((ROOT / 'vendor/msst/source.json').read_text())
    for relative, expected in manifest['files'].items():
        actual = hashlib.sha256((ROOT / 'vendor/msst' / relative).read_bytes()).hexdigest()
        assert actual == expected, f'Vendor hash mismatch: {relative}'
    model = json.loads((ROOT / 'config/model.json').read_text())
    assert hashlib.sha256((ROOT / 'config/melband4.yaml').read_bytes()).hexdigest() == model['config_sha256']
    for relative in ['LICENSE', 'THIRD_PARTY_NOTICES.md', 'ui/assets/fonts/OFL.txt', 'ui/assets/logo.svg', 'requirements/app.lock.txt']:
        assert (ROOT / relative).is_file(), relative
    print('Repository source, model config, assets and vendor hashes: OK')


if __name__ == '__main__':
    main()
