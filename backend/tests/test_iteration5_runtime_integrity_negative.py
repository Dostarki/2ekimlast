"""Iteration 5: negative integrity checks for frontend-only runtime verification."""

import json
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path


REPO_ROOT = Path("/app")
SOURCE_SCRIPT = REPO_ROOT / "scripts" / "package_local_engine.py"
SOURCE_IMPLEMENTATION = REPO_ROOT / "frontend" / "scripts" / "package_local_engine.py"
SOURCE_ARCHIVE = REPO_ROOT / "frontend" / "runtime-assets" / "browser-wheels.zip"
SOURCE_RUNTIME = REPO_ROOT / "frontend" / "public" / "local-runtime"


def _copy_frontend_only_checkout(dst: Path):
    (dst / "scripts").mkdir(parents=True, exist_ok=True)
    (dst / "frontend" / "scripts").mkdir(parents=True, exist_ok=True)
    (dst / "frontend" / "runtime-assets").mkdir(parents=True, exist_ok=True)
    (dst / "frontend" / "public" / "local-runtime").mkdir(parents=True, exist_ok=True)

    shutil.copy2(SOURCE_SCRIPT, dst / "scripts" / "package_local_engine.py")
    shutil.copy2(SOURCE_IMPLEMENTATION, dst / "frontend" / "scripts" / "package_local_engine.py")
    shutil.copy2(SOURCE_ARCHIVE, dst / "frontend" / "runtime-assets" / "browser-wheels.zip")
    shutil.copytree(SOURCE_RUNTIME, dst / "frontend" / "public" / "local-runtime", dirs_exist_ok=True)


def _run_package(checkout: Path):
    return subprocess.run(
        ["python3", "scripts/package_local_engine.py"],
        cwd=checkout,
        capture_output=True,
        text=True,
        timeout=180,
    )


# Module: frontend-only mode rejects tampered manifest hash/runtime metadata.
def test_frontend_only_runtime_rejects_tampered_manifest():
    with tempfile.TemporaryDirectory(prefix="t1_tampered_manifest_") as tmpdir:
        checkout = Path(tmpdir)
        _copy_frontend_only_checkout(checkout)

        manifest_path = checkout / "frontend" / "public" / "local-runtime" / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["version"] = "deadbeefdeadbeef"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        proc = _run_package(checkout)
        assert proc.returncode != 0
        assert "Game bundle/manifest mismatch" in (proc.stdout + proc.stderr)


# Module: frontend-only mode fails when shipped game.zip is missing.
def test_frontend_only_runtime_rejects_missing_game_zip():
    with tempfile.TemporaryDirectory(prefix="t1_missing_game_zip_") as tmpdir:
        checkout = Path(tmpdir)
        _copy_frontend_only_checkout(checkout)

        game_zip = checkout / "frontend" / "public" / "local-runtime" / "game.zip"
        game_zip.unlink()

        proc = _run_package(checkout)
        assert proc.returncode != 0
        assert "Missing browser game asset: game.zip" in (proc.stdout + proc.stderr)


# Module: frontend-only mode rejects unexpected bundle members in game.zip.
def test_frontend_only_runtime_rejects_unexpected_game_bundle_contents():
    with tempfile.TemporaryDirectory(prefix="t1_bad_bundle_members_") as tmpdir:
        checkout = Path(tmpdir)
        _copy_frontend_only_checkout(checkout)

        runtime_dir = checkout / "frontend" / "public" / "local-runtime"
        game_zip = runtime_dir / "game.zip"

        with zipfile.ZipFile(game_zip, "a", zipfile.ZIP_DEFLATED) as bundle:
            bundle.writestr("backend_secret.py", b"print('must never ship')")

        # Keep manifest hash coherent so validation reaches exact-membership check.
        digest = __import__("hashlib").sha256(game_zip.read_bytes()).hexdigest()[:16]
        manifest_path = runtime_dir / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["version"] = digest
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        proc = _run_package(checkout)
        assert proc.returncode != 0
        assert "Invalid game-only bundle contents" in (proc.stdout + proc.stderr)
