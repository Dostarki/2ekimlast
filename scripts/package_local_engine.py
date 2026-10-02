"""Build the browser's game-only bundle. Never ship auth, DB or payment code."""
import hashlib
import json
import urllib.request
import zipfile
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / 'frontend/public/local-runtime'
VERSION = '0.29.3'
CDN = f'https://cdn.jsdelivr.net/pyodide/v{VERSION}/full/'
MODULES = '''world engine combat zombies enemy_types enemy_damage enemy_attacks
enemy_navigation boss_catalog bosses boss_combat game_settings population inventory
weapon_parts spawning bots loot equipment soldier pvp_rewards economy skins'''.split()


def download(url, name, digest=None):
    path = PUBLIC / name
    if path.exists() and (not digest or hashlib.sha256(path.read_bytes()).hexdigest() == digest):
        return
    with urllib.request.urlopen(url, timeout=90) as response:
        data = response.read()
    if digest and hashlib.sha256(data).hexdigest() != digest:
        raise ValueError(f'Integrity check failed: {name}')
    path.write_bytes(data)


def build(download_runtime=False):
    PUBLIC.mkdir(parents=True, exist_ok=True)
    if download_runtime:
        download(CDN + 'pyodide-lock.json', 'pyodide-lock.json')
        lock = json.loads((PUBLIC / 'pyodide-lock.json').read_text())['packages']
        packages = set()
        def include(name):
            name = name.replace('_', '-')
            if name in packages:
                return
            packages.add(name)
            for dep in lock[name]['depends']:
                include(dep)
        for name in ['micropip', 'pydantic', 'cffi']:
            include(name)
        jobs = [(CDN + name, name, None) for name in ['pyodide.js', 'pyodide.asm.js', 'pyodide.asm.wasm', 'python_stdlib.zip']]
        jobs += [(CDN + lock[p]['file_name'], lock[p]['file_name'], lock[p]['sha256']) for p in packages]
        wheel = 'pymunk-7.2.0-cp313-cp313-pyodide_2025_0_wasm32.whl'
        jobs.append((f'https://github.com/viblo/pymunk/releases/download/7.2.0/{wheel}', wheel, None))
        with urllib.request.urlopen('https://pypi.org/pypi/pathfinding/1.0.22/json') as response:
            package = json.load(response)
        wheel_info = next(p for p in package['urls'] if p['filename'].endswith('.whl'))
        jobs.append((wheel_info['url'], wheel_info['filename'], wheel_info['digests']['sha256']))
        with ThreadPoolExecutor(max_workers=6) as pool:
            list(pool.map(lambda args: download(*args), jobs))
    with zipfile.ZipFile(PUBLIC / 'game.zip', 'w', zipfile.ZIP_DEFLATED) as bundle:
        for module in MODULES:
            bundle.write(ROOT / f'backend/{module}.py', f'{module}.py')
        bundle.write(ROOT / 'backend/local_runtime.py', 'local_runtime.py')
        bundle.write(ROOT / 'backend/local_channel.py', 'network.py')
    digest = hashlib.sha256((PUBLIC / 'game.zip').read_bytes()).hexdigest()[:16]
    (PUBLIC / 'manifest.json').write_text(json.dumps({'version': digest, 'runtime': VERSION}))
    print(f'Game bundle: {digest}; {len(MODULES)} game modules, no server secrets')


def verify_runtime():
    lock = json.loads((PUBLIC / 'pyodide-lock.json').read_text())['packages']
    names = set()
    def include(name):
        name = name.replace('_', '-')
        if name in names:
            return
        names.add(name)
        for dependency in lock[name]['depends']:
            include(dependency)
    for name in ['micropip', 'pydantic', 'cffi']:
        include(name)
    required = ['pyodide.js', 'pyodide.asm.js', 'pyodide.asm.wasm', 'python_stdlib.zip', 'game.zip',
                'pymunk-7.2.0-cp313-cp313-pyodide_2025_0_wasm32.whl', 'pathfinding-1.0.22-py3-none-any.whl']
    required += [lock[name]['file_name'] for name in names]
    for filename in required:
        path = PUBLIC / filename
        if not path.is_file() or path.stat().st_size == 0:
            raise RuntimeError(f'Missing browser game asset: {filename}. Run scripts/package_local_engine.py --runtime.')
        if path.suffix in ('.zip', '.whl') and not zipfile.is_zipfile(path):
            raise RuntimeError(f'Invalid browser game archive: {filename}')
    for name in names:
        package = lock[name]
        if hashlib.sha256((PUBLIC / package['file_name']).read_bytes()).hexdigest() != package['sha256']:
            raise RuntimeError(f'Browser dependency checksum mismatch: {name}')
    print(f'Browser runtime verified: {len(required)} required assets')


if __name__ == '__main__':
    import sys
    if '--check' not in sys.argv:
        build('--runtime' in sys.argv)
    verify_runtime()