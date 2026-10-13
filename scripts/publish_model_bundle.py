"""Publish the verified Apache-2.0 ONNX model files to StemFlow's model release."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import urllib.parse
import urllib.request
import http.client

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app_paths import MODEL_DIR


def main():
    git = r'W:\Program Files\Git\cmd\git.exe'
    filled = subprocess.run([git, 'credential', 'fill'], input='protocol=https\nhost=github.com\n\n',
                            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    credentials = dict(line.split('=', 1) for line in filled.stdout.splitlines() if '=' in line)
    token = credentials['password']
    headers = {'Authorization': 'Bearer ' + token, 'Accept': 'application/vnd.github+json',
               'User-Agent': 'StemFlow-model-publisher', 'X-GitHub-Api-Version': '2022-11-28'}
    api = 'https://api.github.com/repos/Chepuxaa/StemFlow/releases'
    tag = 'models-melband4-v2-onnx'
    try:
        release = json.load(urllib.request.urlopen(urllib.request.Request(api + '/tags/' + tag, headers=headers)))
    except urllib.error.HTTPError as exc:
        if exc.code != 404:
            raise
        body = {'tag_name': tag, 'name': 'MelBand SYH v2 - ONNX runtime model', 'prerelease': True,
                'body': 'Converted MelBand four-stem SYH v2 model for StemFlow. Six- and eleven-second graphs share the same weights.\n\nDerived from SYH99999/MelBandRoformer4StemFTLarge, pinned revision 62371baf060e8205915b4e6e3f9459fc016b6dd1. The original model is declared Apache-2.0; the license is included as LICENSE-model.txt. Linear weights use FP16 with FP32 normalization.\n\nThese are model files, not the Windows application. StemFlow downloads and verifies them automatically. The source checkpoint and file SHA-256 hashes are recorded in config/model.json.'}
        request = urllib.request.Request(api, data=json.dumps(body).encode(), headers={**headers, 'Content-Type': 'application/json'}, method='POST')
        release = json.load(urllib.request.urlopen(request))
    manifest = json.loads((ROOT / 'config/model.json').read_text())
    existing = {a['name']: a for a in release.get('assets', [])}
    base = release['upload_url'].split('{')[0]
    for file in manifest['files']:
        path = MODEL_DIR / file['name']
        digest = hashlib.sha256()
        with path.open('rb') as stream:
            while block := stream.read(4 * 1024**2):
                digest.update(block)
        assert path.stat().st_size == file['bytes'] and digest.hexdigest() == file['sha256']
        if file['name'] in existing:
            asset = existing[file['name']]
            if asset['size'] == file['bytes'] and asset.get('digest') == 'sha256:' + file['sha256']:
                print('Already verified:', file['name'], flush=True)
                continue
            raise RuntimeError('Existing model asset differs; refusing to overwrite: ' + file['name'])
        url = urllib.parse.urlsplit(base + '?name=' + urllib.parse.quote(file['name']))
        connection = http.client.HTTPSConnection(url.hostname, timeout=300)
        connection.putrequest('POST', url.path + '?' + url.query)
        for key, value in {**headers, 'Content-Type': 'application/octet-stream', 'Content-Length': str(file['bytes'])}.items():
            connection.putheader(key, value)
        connection.endheaders()
        sent, last = 0, 0
        print('Uploading:', file['name'], flush=True)
        with path.open('rb') as stream:
            while block := stream.read(1024**2):
                connection.send(block)
                sent += len(block)
                if sent - last >= 128 * 1024**2:
                    print(f'{file["name"]}: {sent / file["bytes"]:.0%}', flush=True)
                    last = sent
        response = connection.getresponse()
        asset = json.loads(response.read())
        connection.close()
        if response.status != 201:
            raise RuntimeError(f'Model asset upload failed: HTTP {response.status}')
        assert asset['size'] == file['bytes'] and asset['digest'] == 'sha256:' + file['sha256']
        print('Uploaded and verified:', file['name'], flush=True)
    print(release['html_url'], flush=True)


if __name__ == '__main__':
    main()
