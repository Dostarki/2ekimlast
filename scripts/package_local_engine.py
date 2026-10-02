"""Repository entry point; the build implementation travels with the frontend."""
import runpy
from pathlib import Path

if __name__ == '__main__':
    runpy.run_path(str(Path(__file__).resolve().parents[1] / 'frontend/scripts/package_local_engine.py'),
                  run_name='__main__')