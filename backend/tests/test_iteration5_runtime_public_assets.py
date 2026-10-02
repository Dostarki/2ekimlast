"""Iteration 5: public runtime delivery checks (all required browser assets must serve)."""

import json
import os
from pathlib import Path

import requests


def _base_url() -> str:
    base = (os.environ.get("REACT_APP_BACKEND_URL") or "").strip()
    if not base:
        env_file = Path("/app/frontend/.env")
        if env_file.exists():
            for line in env_file.read_text(encoding="utf-8").splitlines():
                if line.startswith("REACT_APP_BACKEND_URL="):
                    base = line.split("=", 1)[1].strip()
                    if base:
                        os.environ["REACT_APP_BACKEND_URL"] = base
                    break
    if not base:
        raise RuntimeError("REACT_APP_BACKEND_URL is required")
    return base.rstrip("/")


BASE_URL = _base_url()


def _dependencies(lock):
    names = set()

    def include(name):
        normalized = name.replace("_", "-")
        if normalized not in names:
            names.add(normalized)
            for dependency in lock[normalized]["depends"]:
                include(dependency)

    for root in ["micropip", "pydantic", "cffi"]:
        include(root)
    return sorted(names)


# Module: all required runtime files resolve from public preview with non-empty bodies.
def test_public_preview_serves_all_required_runtime_assets():
    runtime_dir = Path("/app/frontend/public/local-runtime")
    lock = json.loads((runtime_dir / "pyodide-lock.json").read_text(encoding="utf-8"))["packages"]

    required = [
        "pyodide.js",
        "pyodide.asm.js",
        "pyodide.asm.wasm",
        "python_stdlib.zip",
        "pyodide-lock.json",
        "game.zip",
        "manifest.json",
        "pymunk-7.2.0-cp313-cp313-pyodide_2025_0_wasm32.whl",
        "pathfinding-1.0.22-py3-none-any.whl",
    ]
    required += [lock[name]["file_name"] for name in _dependencies(lock)]

    assert len(required) == 17
    session = requests.Session()
    for filename in required:
        response = session.get(f"{BASE_URL}/local-runtime/{filename}", timeout=30)
        assert response.status_code == 200, f"missing or non-200 runtime asset: {filename}"
        minimum_size = 10 if filename.endswith(".json") else 64
        assert len(response.content) > minimum_size, f"unexpectedly tiny runtime asset: {filename}"
