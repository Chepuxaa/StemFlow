"""Upload checked Windows assets to a draft, then explicitly publish a prerelease."""
import argparse
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import time

import requests

ROOT = Path(__file__).resolve().parents[1]


class UploadStream:
    def __init__(self, path):
        self.path = path
        self.file = path.open('rb')
        self.total = path.stat().st_size
        self.sent = 0
        self.last_report = 0
        self.started = time.monotonic()

    def __len__(self):
        return self.total

    def read(self, size=-1):
        data = self.file.read(size)
        self.sent += len(data)
        now = time.monotonic()
        if now - self.last_report > 15 or self.sent == self.total:
            elapsed = max(now - self.started, 0.001)
            print(f'{self.path.name}: {self.sent / self.total:.0%}, {self.sent / elapsed / 1e6:.1f} MB/s', flush=True)
            self.last_report = now
        return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository', default='Chepuxaa/StemFlow')
    parser.add_argument('--tag', default='v1.0.0-alpha.1')
    parser.add_argument('--git', default=shutil.which('git'))
    parser.add_argument('--publish', action='store_true')
    parser.add_argument('assets', type=Path, nargs='+')
    args = parser.parse_args()
    for path in args.assets:
        if not path.is_file() or not 0 < path.stat().st_size < 2 * 1024**3:
            raise SystemExit(f'Missing, empty or oversized release asset: {path.name}')
    if not args.git:
        raise SystemExit('Git is required; use --git to specify its executable.')
    token = os.environ.get('GH_TOKEN')
    if not token:
        credential = subprocess.run([args.git, 'credential', 'fill'], input='protocol=https\nhost=github.com\n\n',
                                    capture_output=True, text=True, check=True)
        fields = dict(line.split('=', 1) for line in credential.stdout.splitlines() if '=' in line)
        token = fields.get('password')
    if not token:
        raise SystemExit('No GitHub credential available.')
    session = requests.Session()
    session.headers.update({'Authorization': 'Bearer ' + token, 'Accept': 'application/vnd.github+json',
                            'X-GitHub-Api-Version': '2022-11-28'})
    api = f'https://api.github.com/repos/{args.repository}'
    response = session.get(api + '/releases', timeout=30)
    response.raise_for_status()
    release = next((item for item in response.json() if item['tag_name'] == args.tag), None)
    if release is not None and not release['draft']:
        raise SystemExit('This release is already public; refusing to modify it.')
    body = (ROOT / 'packaging/release-notes.md').read_text(encoding='utf-8')
    if release is None:
        commit = subprocess.run([args.git, 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True,
                                text=True, check=True).stdout.strip()
        response = session.post(api + '/releases', json={'tag_name': args.tag, 'target_commitish': commit,
                                'name': f'StemFlow {args.tag} | Windows CUDA / CPU', 'body': body,
                                'draft': True, 'prerelease': True}, timeout=30)
        response.raise_for_status()
        release = response.json()
    print('Release draft:', release['id'], flush=True)
    upload_url = release['upload_url'].split('{')[0]
    for path in args.assets:
        with path.open('rb') as source:
            digest = hashlib.file_digest(source, 'sha256').hexdigest()
        existing = next((item for item in release['assets'] if item['name'] == path.name), None)
        if existing is not None:
            if existing['size'] == path.stat().st_size and existing.get('digest') == 'sha256:' + digest:
                print('Already verified:', path.name, flush=True)
                continue
            raise SystemExit(f'An unmatched draft asset exists; review it manually: {path.name}')
        stream = UploadStream(path)
        try:
            response = session.post(upload_url, params={'name': path.name}, data=stream,
                                    headers={'Content-Type': 'application/octet-stream',
                                             'Content-Length': str(stream.total)}, timeout=(30, 900))
            response.raise_for_status()
        finally:
            stream.file.close()
        asset = response.json()
        if asset['size'] != path.stat().st_size or asset.get('digest') != 'sha256:' + digest:
            raise SystemExit(f'Uploaded asset verification failed: {path.name}')
        print('Uploaded and verified:', path.name, flush=True)
    if args.publish:
        response = session.patch(api + '/releases/' + str(release['id']),
                                 json={'draft': False, 'prerelease': True, 'body': body}, timeout=30)
        response.raise_for_status()
        print('Published:', response.json()['html_url'], flush=True)
    else:
        print('Assets verified; draft remains unpublished.', flush=True)


if __name__ == '__main__':
    main()
