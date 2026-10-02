"""Iteration 3: offline packaging regression checks for browser wheel archive restore path."""

import os
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path


REPO_ROOT = Path("/app")
SOURCE_BACKEND = REPO_ROOT / "backend"
SOURCE_SCRIPT = REPO_ROOT / "scripts" / "package_local_engine.py"
SOURCE_IMPLEMENTATION = REPO_ROOT / "frontend" / "scripts" / "package_local_engine.py"
SOURCE_ARCHIVE = REPO_ROOT / "frontend" / "runtime-assets" / "browser-wheels.zip"
SOURCE_RUNTIME = REPO_ROOT / "frontend" / "public" / "local-runtime"


def _copy_minimal_checkout(dst: Path):
    (dst / "backend").mkdir(parents=True, exist_ok=True)
    (dst / "scripts").mkdir(parents=True, exist_ok=True)
    (dst / "frontend" / "scripts").mkdir(parents=True, exist_ok=True)
    (dst / "frontend" / "runtime-assets").mkdir(parents=True, exist_ok=True)
    (dst / "frontend" / "public" / "local-runtime").mkdir(parents=True, exist_ok=True)

    for py_file in SOURCE_BACKEND.glob("*.py"):
        shutil.copy2(py_file, dst / "backend" / py_file.name)

    shutil.copy2(SOURCE_SCRIPT, dst / "scripts" / "package_local_engine.py")
    shutil.copy2(SOURCE_IMPLEMENTATION, dst / "frontend" / "scripts" / "package_local_engine.py")
    shutil.copy2(SOURCE_ARCHIVE, dst / "frontend" / "runtime-assets" / "browser-wheels.zip")

    for asset in SOURCE_RUNTIME.iterdir():
        if asset.suffix == ".whl":
            continue
        if asset.is_file():
            shutil.copy2(asset, dst / "frontend" / "public" / "local-runtime" / asset.name)


def _offline_env(checkout_root: Path):
    env = os.environ.copy()
    env["PYTHONPATH"] = str(checkout_root)
    return env


def _write_sitecustomize_block_network(checkout_root: Path):
    (checkout_root / "sitecustomize.py").write_text(
        """
import urllib.request
def _blocked(*_args, **_kwargs):
    raise RuntimeError('network blocked during offline packaging test')
urllib.request.urlopen = _blocked
""".strip(),
        encoding="utf-8",
    )


# Module: ordinary offline build restores missing wheels from committed archive.
def test_package_local_engine_restores_wheels_offline_and_verifies_runtime():
    with tempfile.TemporaryDirectory(prefix="t1_pkg_offline_ok_") as tmpdir:
        checkout = Path(tmpdir)
        _copy_minimal_checkout(checkout)
        _write_sitecustomize_block_network(checkout)

        runtime_dir = checkout / "frontend" / "public" / "local-runtime"
        assert list(runtime_dir.glob("*.whl")) == []

        proc = subprocess.run(
            ["python3", "scripts/package_local_engine.py"],
            cwd=checkout,
            env=_offline_env(checkout),
            capture_output=True,
            text=True,
            timeout=180,
        )
        assert proc.returncode == 0, f"offline package script failed\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
        assert "Browser runtime verified" in proc.stdout

        wheels = sorted(runtime_dir.glob("*.whl"))
        assert len(wheels) == 10

        with zipfile.ZipFile(checkout / "frontend" / "runtime-assets" / "browser-wheels.zip") as bundle:
            members = sorted(bundle.namelist())
            assert len(members) == 10
            assert all(name.endswith(".whl") for name in members)
            for wheel_name in members:
                extracted = runtime_dir / wheel_name
                assert extracted.is_file()
                assert extracted.read_bytes() == bundle.read(wheel_name)


# Module: security guard rejects path-traversal archive members.
def test_package_local_engine_rejects_archive_path_traversal_members():
    with tempfile.TemporaryDirectory(prefix="t1_pkg_offline_badzip_") as tmpdir:
        checkout = Path(tmpdir)
        _copy_minimal_checkout(checkout)

        archive_path = checkout / "frontend" / "runtime-assets" / "browser-wheels.zip"
        with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as bad_zip:
            bad_zip.writestr("../escape.whl", b"malicious")

        proc = subprocess.run(
            ["python3", "scripts/package_local_engine.py"],
            cwd=checkout,
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert proc.returncode != 0
        assert "Unexpected browser archive member" in (proc.stderr + proc.stdout)


# Module: clear failure when both archive and wheel assets are missing.
def test_package_local_engine_missing_archive_and_wheel_fails_clearly():
    with tempfile.TemporaryDirectory(prefix="t1_pkg_offline_missing_") as tmpdir:
        checkout = Path(tmpdir)
        _copy_minimal_checkout(checkout)

        archive = checkout / "frontend" / "runtime-assets" / "browser-wheels.zip"
        archive.unlink()

        runtime_dir = checkout / "frontend" / "public" / "local-runtime"
        # Ensure required wheel truly absent.
        for wheel in runtime_dir.glob("*.whl"):
            wheel.unlink()

        proc = subprocess.run(
            ["python3", "scripts/package_local_engine.py"],
            cwd=checkout,
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert proc.returncode != 0
        combined = proc.stderr + proc.stdout
        assert "Missing browser game asset" in combined
