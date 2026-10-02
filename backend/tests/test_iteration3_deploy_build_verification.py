"""Iteration 3: deployment-readiness checks for clean runtime + public read-only APIs."""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest
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


def _api(path: str) -> str:
    return f"{BASE_URL}/api{path}"


# Module: external preview read-only endpoint contract checks.
def test_preview_read_only_endpoints_contract():
    session = requests.Session()

    root = session.get(_api("/"), timeout=20)
    assert root.status_code == 200
    root_data = root.json()
    assert root_data.get("name") == "LastZHood"
    assert root_data.get("status") == "online"

    status = session.get(_api("/status"), timeout=20)
    assert status.status_code == 200
    status_data = status.json()
    assert isinstance(status_data.get("online"), int)
    assert status_data.get("simulation") == "local"
    assert status_data.get("capacity") == 200

    world = session.get(_api("/world"), timeout=20)
    assert world.status_code == 200
    world_data = world.json()
    assert isinstance(world_data.get("chunks"), list)
    assert len(world_data["chunks"]) > 0

    weapons = session.get(_api("/weapons"), timeout=20)
    assert weapons.status_code == 200
    weapons_data = weapons.json()
    assert isinstance(weapons_data, dict)
    assert "glock18" in weapons_data

    leaderboard = session.get(_api("/leaderboard"), timeout=20)
    assert leaderboard.status_code == 200
    leaderboard_data = leaderboard.json()
    assert isinstance(leaderboard_data, list)

    early_cfg = session.get(_api("/early/config"), timeout=20)
    assert early_cfg.status_code == 200
    cfg_data = early_cfg.json()
    assert isinstance(cfg_data, dict)
    # Early config shape can evolve; validate meaningful, non-empty public config payload.
    assert len(cfg_data.keys()) > 0
    assert any(key in cfg_data for key in ("tasks", "campaign", "x_profile_url", "share_text"))


# Module: clean production-only venv verifies FastAPI lifespan + handler execution.
def test_clean_runtime_lifespan_and_handlers_pass():
    runtime_python = Path("/tmp/lastzhood-runtime/bin/python")
    if not runtime_python.exists():
        pytest.skip("Clean runtime python missing: /tmp/lastzhood-runtime/bin/python")

    with tempfile.TemporaryDirectory(prefix="t1_clean_runtime_") as tmpdir:
        probe = Path(tmpdir) / "probe_clean_runtime.py"
        probe.write_text(
            """
import asyncio
import json
import sys
sys.path.insert(0, '/app/backend')
import server

async def main():
    async with server.lifespan(server.app):
        root = await server.root()
        status = await server.status()
        world = await server.world()
        weapons = await server.weapons()
        leaderboard = await server.leaderboard()
        api_routes = [r.path for r in server.app.routes if r.path.startswith('/api')]
        print(json.dumps({
            'root_status': root.get('status'),
            'status_simulation': status.get('simulation'),
            'world_chunks': len(world.get('chunks', [])),
            'weapons_count': len(weapons),
            'leaderboard_type': isinstance(leaderboard, list),
            'api_route_count': len(api_routes)
        }))

asyncio.run(main())
""".strip(),
            encoding="utf-8",
        )

        result = subprocess.run(
            [str(runtime_python), str(probe)],
            capture_output=True,
            text=True,
            timeout=180,
            cwd="/app/backend",
        )

        assert result.returncode == 0, f"clean runtime probe failed\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        payload = json.loads(result.stdout.strip().splitlines()[-1])
        assert payload["root_status"] == "online"
        assert payload["status_simulation"] == "local"
        assert payload["world_chunks"] > 0
        assert payload["weapons_count"] > 0
        assert payload["leaderboard_type"] is True
        assert payload["api_route_count"] >= 55


# Module: runtime asset response integrity (binary archives should not be HTML).
def test_local_runtime_assets_serve_binary_content_types():
    asset_paths = [
        "/local-runtime/pyodide.asm.wasm",
        "/local-runtime/python_stdlib.zip",
        "/local-runtime/game.zip",
        "/local-runtime/pathfinding-1.0.22-py3-none-any.whl",
    ]

    session = requests.Session()
    for asset in asset_paths:
        response = session.get(f"{BASE_URL}{asset}", timeout=30)
        assert response.status_code == 200
        body_start = response.content[:256].lower()
        assert b"<html" not in body_start
        assert len(response.content) > 128
