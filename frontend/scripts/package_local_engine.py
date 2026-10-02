"""Prepare game-only browser assets in repository OR frontend-only Docker layouts."""
import argparse
import hashlib
import json
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

FRONTEND = Path(__file__).resolve().parents[1]
PUBLIC = FRONTEND / 'public/local-runtime'
WHEEL_ARCHIVE = FRONTEND / 'runtime-assets/browser-wheels.zip'
VERSION = '0.29.3'
CDN = f'https://cdn.jsdelivr.net/pyodide/v{VERSION}/full/'
MODULES = '''world engine combat zombies enemy_types enemy_damage enemy_attacks
enemy_navigation boss_catalog bosses boss_combat game_settings population inventory
weapon_parts spawning bots loot equipment soldier pvp_rewards economy skins'''.split()


def dependencies(lock):
    names = set()
    def include(name):
        name = name.replace('_', '-')
        if name not in names:
            names.add(name)
            for dependency in lock[name]['depends']:
                include(dependency)
    for name in ['micropip', 'pydantic', 'cffi']:
        include(name)
    return sorted(names)


def archive_wheels():
    WHEEL_ARCHIVE.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(WHEEL_ARCHIVE, 'w', zipfile.ZIP_DEFLATED) as bundle:
        for wheel in sorted(PUBLIC.glob('*.whl')):
            info = zipfile.ZipInfo(wheel.name, date_time=(2020, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            bundle.writestr(info, wheel.read_bytes())


def restore_wheels():
    if not WHEEL_ARCHIVE.is_file():
        return  # Complete legacy checkouts can still pass strict verification.
    with zipfile.ZipFile(WHEEL_ARCHIVE) as bundle:
        for name in bundle.namelist():
            if Path(name).name != name or not name.endswith('.whl'):
                raise RuntimeError(f'Unexpected browser archive member: {name}')
            destination = PUBLIC / name
            if not destination.is_file() or destination.read_bytes() != bundle.read(name):
                bundle.extract(name, PUBLIC)


def download(url, name, digest=None):
    path = PUBLIC / name
    if path.exists() and (not digest or hashlib.sha256(path.read_bytes()).hexdigest() == digest):
        return
    with urllib.request.urlopen(url, timeout=90) as response:
        data = response.read()
    if digest and hashlib.sha256(data).hexdigest() != digest:
        raise ValueError(f'Integrity check failed: {name}')
    with path.open('wb') as output:
        output.write(data)


def refresh_runtime():
    download(CDN + 'pyodide-lock.json', 'pyodide-lock.json')
    lock = json.loads((PUBLIC / 'pyodide-lock.json').read_text())['packages']
    jobs = [(CDN + name, name, None) for name in
            ['pyodide.js', 'pyodide.asm.js', 'pyodide.asm.wasm', 'python_stdlib.zip']]
    jobs += [(CDN + lock[p]['file_name'], lock[p]['file_name'], lock[p]['sha256']) for p in dependencies(lock)]
    wheel = 'pymunk-7.2.0-cp313-cp313-pyodide_2025_0_wasm32.whl'
    jobs.append((f'https://github.com/viblo/pymunk/releases/download/7.2.0/{wheel}', wheel, None))
    with urllib.request.urlopen('https://pypi.org/pypi/pathfinding/1.0.22/json', timeout=90) as response:
        package = json.load(response)
    info = next(p for p in package['urls'] if p['filename'].endswith('.whl'))
    jobs.append((info['url'], info['filename'], info['digests']['sha256']))
    with ThreadPoolExecutor(max_workers=6) as pool:
        list(pool.map(lambda args: download(*args), jobs))
    archive_wheels()


def build(source_dir, download_runtime=False):
    PUBLIC.mkdir(parents=True, exist_ok=True)
    refresh_runtime() if download_runtime else restore_wheels()
    if not source_dir.is_dir():
        # Docker may COPY only frontend/. Verify, never invent, the shipped bundle.
        print('Frontend-only build: validating packaged game bundle')
        return
    files = {f'{module}.py': f'{module}.py' for module in MODULES}
    files.update({'local_runtime.py': 'local_runtime.py', 'network.py': 'local_channel.py'})
    with zipfile.ZipFile(PUBLIC / 'game.zip', 'w', zipfile.ZIP_DEFLATED) as bundle:
        for name, source in sorted(files.items()):
            info = zipfile.ZipInfo(name, date_time=(2020, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            bundle.writestr(info, (source_dir / source).read_bytes())
    digest = hashlib.sha256((PUBLIC / 'game.zip').read_bytes()).hexdigest()[:16]
    (PUBLIC / 'manifest.json').write_text(json.dumps({'version': digest, 'runtime': VERSION}))
    print(f'Game bundle: {digest}; {len(MODULES)} game modules, no server secrets')


def verify_runtime():
    lock = json.loads((PUBLIC / 'pyodide-lock.json').read_text())['packages']
    required = ['pyodide.js', 'pyodide.asm.js', 'pyodide.asm.wasm', 'python_stdlib.zip', 'game.zip',
                'pymunk-7.2.0-cp313-cp313-pyodide_2025_0_wasm32.whl', 'pathfinding-1.0.22-py3-none-any.whl']
    required += [lock[name]['file_name'] for name in dependencies(lock)]
    for filename in required:
        path = PUBLIC / filename
        if not path.is_file() or path.stat().st_size == 0:
            raise RuntimeError(f'Missing browser game asset: {filename}. Run scripts/package_local_engine.py --runtime.')
        if path.suffix in ('.zip', '.whl') and not zipfile.is_zipfile(path):
            raise RuntimeError(f'Invalid browser game archive: {filename}')
    for name in dependencies(lock):
        package = lock[name]
        if hashlib.sha256((PUBLIC / package['file_name']).read_bytes()).hexdigest() != package['sha256']:
            raise RuntimeError(f'Browser dependency checksum mismatch: {name}')
    manifest = json.loads((PUBLIC / 'manifest.json').read_text())
    digest = hashlib.sha256((PUBLIC / 'game.zip').read_bytes()).hexdigest()[:16]
    if manifest != {'version': digest, 'runtime': VERSION}:
        raise RuntimeError('Game bundle/manifest mismatch; regenerate from the backend sources.')
    with zipfile.ZipFile(PUBLIC / 'game.zip') as bundle:
        expected = {f'{module}.py' for module in MODULES} | {'local_runtime.py', 'network.py'}
        if set(bundle.namelist()) != expected or bundle.testzip() is not None:
            raise RuntimeError('Invalid game-only bundle contents; regenerate from backend sources.')
    print(f'Browser runtime verified: {len(required)} required assets at {PUBLIC}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime', action='store_true')
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--source-dir', type=Path)
    parser.add_argument('--public-dir', type=Path)
    args = parser.parse_args()
    if args.public_dir:
        PUBLIC = args.public_dir.resolve()
    if args.source_dir and not args.source_dir.is_dir():
        parser.error('--source-dir must point to an existing backend source directory')
    if not args.check:
        build(args.source_dir or FRONTEND.parent / 'backend', args.runtime)
    verify_runtime()