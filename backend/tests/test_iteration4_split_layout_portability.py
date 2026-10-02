"""Iteration 4: split-layout portability reproductions for production CRACO packaging hook."""

import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path


REPO_ROOT = Path("/app")
SOURCE_BACKEND = REPO_ROOT / "backend"
SOURCE_SCRIPT = REPO_ROOT / "scripts" / "package_local_engine.py"
SOURCE_IMPLEMENTATION = REPO_ROOT / "frontend" / "scripts" / "package_local_engine.py"
SOURCE_ARCHIVE = REPO_ROOT / "frontend" / "runtime-assets" / "browser-wheels.zip"
SOURCE_RUNTIME = REPO_ROOT / "frontend" / "public" / "local-runtime"
SOURCE_CRACO = REPO_ROOT / "frontend" / "craco.config.js"
SOURCE_NODE_MODULES = REPO_ROOT / "frontend" / "node_modules"


def _copy_workspace_tree(workspace_root: Path):
    (workspace_root / "backend").mkdir(parents=True, exist_ok=True)
    (workspace_root / "scripts").mkdir(parents=True, exist_ok=True)
    (workspace_root / "frontend" / "scripts").mkdir(parents=True, exist_ok=True)
    (workspace_root / "frontend" / "runtime-assets").mkdir(parents=True, exist_ok=True)
    (workspace_root / "frontend" / "public" / "local-runtime").mkdir(parents=True, exist_ok=True)

    for py_file in SOURCE_BACKEND.glob("*.py"):
        shutil.copy2(py_file, workspace_root / "backend" / py_file.name)

    shutil.copy2(SOURCE_SCRIPT, workspace_root / "scripts" / "package_local_engine.py")
    shutil.copy2(SOURCE_IMPLEMENTATION, workspace_root / "frontend" / "scripts" / "package_local_engine.py")
    shutil.copy2(SOURCE_ARCHIVE, workspace_root / "frontend" / "runtime-assets" / "browser-wheels.zip")
    shutil.copytree(SOURCE_RUNTIME, workspace_root / "frontend" / "public" / "local-runtime", dirs_exist_ok=True)


def _copy_split_frontend_build_tree(frontend_build_root: Path):
    app_root = frontend_build_root / "app"
    (app_root / "public" / "local-runtime").mkdir(parents=True, exist_ok=True)
    (app_root / "scripts").mkdir(parents=True, exist_ok=True)
    (app_root / "runtime-assets").mkdir(parents=True, exist_ok=True)
    shutil.copy2(SOURCE_CRACO, app_root / "craco.config.js")
    shutil.copy2(SOURCE_IMPLEMENTATION, app_root / "scripts" / "package_local_engine.py")
    shutil.copy2(SOURCE_ARCHIVE, app_root / "runtime-assets" / "browser-wheels.zip")
    shutil.copytree(SOURCE_RUNTIME, app_root / "public" / "local-runtime", dirs_exist_ok=True)
    os.symlink(SOURCE_NODE_MODULES, app_root / "node_modules")
    return app_root


# Module: baseline repository-shaped frontend production CRACO hook remains healthy.
def test_repo_layout_craco_production_hook_passes():
    proc = subprocess.run(
        ["node", "-e", "require('./craco.config.js')"],
        cwd=str(REPO_ROOT / "frontend"),
        capture_output=True,
        text=True,
        timeout=180,
        env={**os.environ, "NODE_ENV": "production"},
    )
    assert proc.returncode == 0, f"repo-layout craco production evaluation failed\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
    assert "Browser runtime verified" in proc.stdout


# Module: frontend-only Docker COPY must work without sibling scripts or backend.
def test_split_layout_craco_prepares_active_frontend_public():
    with tempfile.TemporaryDirectory(prefix="t1_split_craco_lookup_") as tmpdir:
        root = Path(tmpdir)
        workspace_root = root / "workspace"
        frontend_build_root = root / "frontend-build"

        _copy_workspace_tree(workspace_root)
        app_root = _copy_split_frontend_build_tree(frontend_build_root)
        for wheel in (app_root / "public" / "local-runtime").glob("*.whl"):
            wheel.unlink()

        proc = subprocess.run(
            ["node", "-e", "require('./craco.config.js')"],
            cwd=str(app_root),
            capture_output=True,
            text=True,
            timeout=180,
            env={**os.environ, "NODE_ENV": "production"},
        )

        combined = proc.stdout + proc.stderr
        assert proc.returncode == 0, combined
        assert 'Frontend-only build: validating packaged game bundle' in combined
        assert 'Browser runtime verified' in combined
        assert len(list((app_root / 'public' / 'local-runtime').glob('*.whl'))) == 10


# Module: explicit output/source arguments target the build COPY, not source workspace.
def test_split_layout_python_packaging_targets_explicit_build_public():
    with tempfile.TemporaryDirectory(prefix="t1_split_python_target_") as tmpdir:
        root = Path(tmpdir)
        workspace_root = root / "workspace"
        frontend_build_root = root / "frontend-build"

        _copy_workspace_tree(workspace_root)
        app_root = _copy_split_frontend_build_tree(frontend_build_root)

        workspace_runtime = workspace_root / "frontend" / "public" / "local-runtime"
        build_runtime = app_root / "public" / "local-runtime"

        for wheel in workspace_runtime.glob("*.whl"):
            wheel.unlink()
        for wheel in build_runtime.glob("*.whl"):
            wheel.unlink()

        build_manifest_mtime_before = (build_runtime / "manifest.json").stat().st_mtime_ns
        time.sleep(0.01)

        proc = subprocess.run(
            ["python3", str(workspace_root / "scripts" / "package_local_engine.py"),
             '--source-dir', str(workspace_root / 'backend'), '--public-dir', str(build_runtime)],
            cwd=str(workspace_root),
            capture_output=True,
            text=True,
            timeout=180,
        )

        assert proc.returncode == 0, f"split-layout python packaging failed\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
        assert "Browser runtime verified" in proc.stdout

        workspace_wheels = sorted(workspace_runtime.glob("*.whl"))
        build_wheels = sorted(build_runtime.glob("*.whl"))
        assert len(workspace_wheels) == 0
        assert len(build_wheels) == 10

        build_manifest_mtime_after = (build_runtime / "manifest.json").stat().st_mtime_ns
        assert build_manifest_mtime_after > build_manifest_mtime_before
