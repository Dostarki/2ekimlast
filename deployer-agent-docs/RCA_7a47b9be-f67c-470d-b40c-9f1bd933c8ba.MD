# RCA — LastZHood (lasthood-dev) build failure

Deployment: e086baef-6d03-4b82-9541-6531316f7be8 (type: initial, arm64, tier_0, frontend_type: cloudflare)
Failed run: 7a47b9be-f67c-470d-b40c-9f1bd933c8ba
Cloud Build: prod-deployer-app-builder:dc11ad5c-9544-4138-a14c-19ab8ea3dab6 (AWS CodeBuild)
Failing step: `build` (build_image). All later steps (mongodb_migrate, manage_secrets, deploy, health_check) = "not run: an earlier deploy step failed".

## 1. Which cloud subprocess actually failed

The CodeBuild `build` phase runs TWO things concurrently:
- **Foreground:** `build-frontend-artifacts.sh` (builds the React/Pyodide frontend and uploads it to R2/S3 for the Cloudflare worker).
- **Background (`$BUILD_PID`):** `docker buildx build ... -f Dockerfile.cloudbuild --push` (builds the backend container image).

Evidence from the run error tail:
- `[FRONTEND_BUILD] Build completed successfully!` and artifacts uploaded (incl. `local-runtime/pyodide.asm.wasm`) → **the frontend-artifacts subprocess SUCCEEDED.**
- `wait $BUILD_PID` → `. Reason: exit status 1` → **the `docker buildx` image build FAILED.**
- POST_BUILD: `ERROR: 287883095218.dkr.ecr.us-west-2.amazonaws.com/customers-app:7a47b9be-...: not found` → the image was never pushed, confirming the buildx build is what died.

So the user's observation ("FRONTEND_BUILD completed but BUILD exit 1") is explained: the frontend-artifacts build is a *different* subprocess from the docker image build. The failure is the **docker image build**, not the frontend artifacts.

## 2. Which stage inside the docker build failed

The buildx error detail is NOT retrievable: this is AWS CodeBuild, and the log read is capped to the first ~500 lines, which are entirely buildspec echo + the frontend-artifacts `cp` output. The `docker buildx`/buildkit output (and its failing-step summary) is beyond that window and never appears. So the exact RUN line + exit code could not be read directly.

However, the failure was localized by comparison + reproduction:
- Earlier runs 21010d71 and 7140834b (same job) DID capture a buildx summary: `failed step [frontend-build 13/14] ... Command failed: python3 /scripts/package_local_engine.py` — i.e. the Pyodide/local-runtime packaging in the **frontend-build stage**.
- Runs dcd653f7 and 7a47b9be (latest) no longer carry that summary, run ~1 min longer (~6m06s vs ~4.5–5m), and the frontend stage reproduces clean (see below). → the failure moved PAST the frontend stage into the **backend-build stage** of `Dockerfile.cloudbuild` (the `pip install` + the `compileall` of all site-packages).

## 3. What was ruled OUT (with reproduction in an eph sandbox on the run's source)

- **Dependency resolution / missing wheel — RULED OUT.** `pip download --only-binary=:all:` for aarch64 (manylinux2014/2_17/2_28) resolved EVERY pinned package with no "No matching distribution"; a full `pip install --no-deps` of the entire requirements (litellm from whl, emergentintegrations from the Emergent CDN index) succeeded. All packages ship aarch64 wheels.
- **Missing Pyodide/local-runtime assets — RULED OUT.** `frontend/public/local-runtime/` is committed (15MB: python_stdlib.zip, pyodide.asm.wasm, wheels, game.zip, manifest). Running `python3 scripts/package_local_engine.py` exactly as `craco.config.js` invokes it printed `Browser runtime verified: 15 required assets`, EXIT 0.
- **Missing COPY source path — RULED OUT.** `pip-cache/pip-wheels` and `pip-cache/pip-bin` both exist, so the backend-stage `COPY pip-cache/...` lines do not fail.
- **Network — not the cause.** All remote fetches (CDN wheels, R2 sync) have retry loops and the repro fetched from the Emergent CDN fine; frontend R2 upload succeeded.
- **Disk — unlikely.** Pre-fix installed footprint was ~550 MiB; CodeBuild has GBs of scratch. Not the limiting resource.

## 4. Root cause (strongly supported; OOM not directly observed)

The backend `requirements.txt` was a full pip-freeze of the preview env — **~145 packages / ~550 MiB installed** — the large majority of which the backend never imports. Static import scan of `backend/*.py`:
- 0 import files: numpy, pandas, tokenizers, huggingface_hub, transformers, tiktoken, google-generativeai, google-genai, scipy, sklearn, boto3, litellm, emergentintegrations, openai, stripe, jq, ckzg, py_ecc, eth_abi (plus dev tooling: black, flake8, mypy, isort, pytest, pytest-xdist, pycodestyle, pyflakes).
- Actually used: pymunk (1), pathfinding (1), eth_account (4), PIL/pillow (1), fastapi/motor/pydantic/dotenv (core).

Installing + byte-compiling (`python -m compileall` over ALL of site-packages) this many heavy C/Rust wheels, on an arm64 build machine, concurrently with the parallel frontend-artifacts build, is the most probable cause of the backend-stage failure (resource exhaustion / OOM-style kill). This also explains the symptom pattern: no clean buildx "failed step" summary (consistent with a killed process rather than a normal non-zero command) and the ~1 min longer runtime before death.

This is **strongly supported but not directly observed** — CodeBuild's log window does not expose the buildkit exit line, so an exact OOM (exit 137) could not be printed. It is NOT a dependency-resolution, missing-asset, missing-COPY, or network error — those were each reproduced as healthy.

## 5. Do the completed code fixes address it?

Yes — directly. The reported optimization (production lock trimmed ~145→46 packages, installed ~550.8 MiB→79.5 MiB, no business/auth changes, FastAPI lifespan+Mongo handlers pass on a clean venv; browser wheels moved to `scripts/assets/browser-wheels.zip` with offline-restore tests passing; source maps disabled) removes exactly the dead-weight packages identified above and cuts the install + compileall footprint ~7x. That is the most effective lever against the backend-stage resource pressure that is the probable root cause, and it also reduces the "excessive build duration" and final image size.

## 6. Recommended next action

Redeploy to verify. Expected outcome: the backend image build completes and the image is pushed. If it STILL fails after the ~7x trim, the residual cause is build-machine memory on the platform side (escalate to Emergent) — and the lighter frontend log should also let the next build surface the actual buildkit error inside the readable log window for a precise confirmation.
