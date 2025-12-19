# SWE-bench Docker Architecture

This document explains how the official SWE-bench evaluation harness uses Docker to execute and grade data points. It focuses on the three-layer image stack, the build/execution lifecycle, and how the validator in this repository plugs into that flow. The intent is to give enough detail to debug and extend the system without reading the entire harness source.

## High-level flow

1. Start from a **base image** with generic tooling (Python, git, system packages).
2. Build a **repository environment image** that installs repo-level dependencies pinned to the dataset's `base_commit`.
3. Build **per-instance images** that layer issue-specific artifacts on top of the environment image (e.g., fetched repository state).
4. For each prediction (patch), spin up a container from the instance image, apply the patch, and run the test commands defined by the dataset entry (`FAIL_TO_PASS` and `PASS_TO_PASS`).
5. Parse test logs to decide whether the instance is resolved and write per-instance reports plus a run summary.

Every run is identified by a `run_id`. Logs and reports live under `logs/run_evaluation/<run_id>/...`.

## Layer 1: Base images

* Purpose: stable starting point with OS tooling, Python, git, curl, and Docker utilities used by the harness.
* Built once per architecture; reused across datasets and repositories.
* Lives under the Docker namespace `swebench` by default (configurable).
* Contains:
  - OS packages (build-essential, git, libssl, libffi, etc.)
  - Python runtime and `pip`
  - Non-Python tools frequently used by repos (e.g., `curl`, `bash`, `patch`)
* Rarely rebuilt; only refreshed when the harness updates its foundational dependencies.

## Layer 2: Environment images

* Purpose: capture repository-specific dependencies for a given dataset commit.
* One environment image per repository per base commit (e.g., `swebench/astropy:3832210`).
* Build steps:
  1. Clone the target repo and check out the dataset's `base_commit`.
  2. Install Python requirements (pip/conda depending on repo), system packages, and any harness helpers.
  3. Cache the resulting image so subsequent instances from the same repo reuse it.
* When rebuilt:
  - On first use for a repo/base commit pair.
  - When `--force_rebuild` is set.
  - When cache policy (`cache_level`) discards environment images.
* Where requirements are installed:
  - Python deps inside the image's virtual environment (or system site-packages if the repo uses that).
  - System packages via apt/yum as needed by the repo’s `environment.yml`/`requirements.txt`/`pyproject`.

## Layer 3: Instance images

* Purpose: hold the repository state and metadata specific to a single dataset instance.
* Built from the environment image and tagged with the instance key (e.g., `swebench/astropy__astropy-11693:latest`).
* Build steps:
  1. Copy the environment image as the base.
  2. Materialize any instance-level fixtures (e.g., prepared repos, cached datasets, additional scripts).
  3. Record the evaluation script for the instance (stored under `logs/run_evaluation/<run_id>/<model>/<instance_id>/eval.sh` during runs).
* Instance images are cheap to rebuild; they may be discarded after a run depending on `cache_level` and `clean` flags.

## Image lifecycle controls

* `cache_level` controls cleanup:
  - `none`: remove everything after the run.
  - `base`: keep only base images.
  - `env`: keep base + environment images (default in this repo).
  - `instance`: keep everything.
* `clean`: if true, remove images above the cache level even if they already existed.
* `force_rebuild`: ignore cached layers and rebuild environment + instance images.
* `namespace`: Docker namespace/prefix. Set to `none` to disable namespacing; otherwise tags look like `namespace/repo__id:tag`.
* `instance_image_tag`: tag used for instance images (default `latest`).

## Test execution flow inside a container

1. **Container start**: The harness calls `docker.from_env().containers.run(...)` via `build_container`, using the instance image as the base. Container workdir is usually `/repo`.
2. **Patch delivery**: The validator writes the model patch to `patch.diff` under the run log directory, then copies it into the container path specified by `DOCKER_PATCH`.
3. **Patch application**: The harness tries multiple patch commands in order:
   - `git apply --verbose patch.diff`
   - `git apply --verbose --reject patch.diff`
   - `patch --batch --fuzz=5 -p1 -i patch.diff`
   If all fail, the run is marked with `APPLY_PATCH_FAIL` and the instance errors out.
4. **Pre-test snapshot**: `git diff` is captured before running tests for debugging.
5. **Eval script staging**: The test script (`eval.sh`) is generated from the dataset’s test specification and copied into the container root.
6. **Test execution**: The harness runs `/bin/bash /eval.sh` with a configurable timeout. Output is streamed and written to `test_output.txt`. Timeout produces a hard failure with the timeout message appended.
7. **Post-test snapshot**: Another `git diff` is collected to highlight mutations from tests.
8. **Log parsing**: `get_logs_eval` parses `test_output.txt` to map each test case to PASS/FAIL/NOT RUN. The harness then builds a report via `get_eval_report`.
9. **Grading**:
   - `FAIL_TO_PASS` tests must pass to count as a resolution.
   - `PASS_TO_PASS` tests must remain passing (regressions here fail the instance).
   - Some repos are marked “fail-only,” in which case only `FAIL_TO_PASS` matters.
10. **Report writing**: Per-instance report goes to `logs/run_evaluation/<run_id>/<model>/<instance_id>/report.json`. A run-level summary (counts of resolved/unresolved/error) is written to `<model>.<run_id>.json` in the working directory.

## Example: evaluating a single instance

Below is a simplified sequence the harness performs for `astropy__astropy-11693` using the validator in this repo:

```
# 1) Create temporary dataset and predictions files
.swe-bench-validator/dataset.validator-123.json
.swe-bench-validator/predictions.validator-123.json

# 2) Build environment image (if missing)
docker build -t swebench/astropy:3832210580d5 ...

# 3) Build instance image
docker build -t swebench/astropy__astropy-11693:latest ...

# 4) Run container, apply patch, execute tests with timeout
docker run --name astropy__astropy-11693-<run_id> swebench/astropy__astropy-11693:latest
git apply patch.diff || patch -p1 -i patch.diff
/bin/bash /eval.sh  # runs FAIL_TO_PASS + PASS_TO_PASS tests

# 5) Collect logs and write reports
logs/run_evaluation/<run_id>/validator/astropy__astropy-11693/test_output.txt
logs/run_evaluation/<run_id>/validator/astropy__astropy-11693/report.json
validator.<run_id>.json  # run summary
```

## Integration with this validator

* The CLI (`swe_bench_validator_custom/cli.py`) converts the selected data points into:
  - A temporary dataset JSON consumed by `load_swebench_dataset`.
  - A predictions JSON where `model_patch` is the golden patch from the data point.
* The CLI then calls `swebench.harness.run_evaluation.main` with:
  - `cache_level=env` by default to reuse environment images.
  - Configurable `timeout`, `max_workers`, and `force_rebuild` flags.
* Run artifacts are written under `.swe-bench-validator` plus the harness’s `logs/run_evaluation` tree. CI surfaces failures by reading these reports.

## When and where requirements install

* Python dependencies are installed during environment image build (Layer 2). The harness inspects repository manifests (`requirements.txt`, `environment.yml`, `setup.py`, or `pyproject.toml`) and installs them inside the image so test runs do not need network access.
* Instance image builds do not install additional Python deps; they reuse the environment image’s environment. They may add scripts or cached assets referenced by the dataset.
* During test execution, the container has all dependencies pre-installed; only the model patch is injected at runtime.

## Timeout handling

* The harness enforces a per-instance timeout (default 1800s upstream). The validator exposes `--timeout` to lower this (default 1200s here).
* On timeout, `test_output.txt` appends `Timeout error: <seconds> exceeded.` and the instance is marked unresolved/error.
* Long builds can also be constrained by setting `max_workers` to avoid overwhelming the host.

## Cleanup expectations

* After a run:
  - Containers are removed via `cleanup_container`.
  - Images are pruned based on `cache_level` and `clean`.
  - Logs remain on disk for inspection.
* If the process is interrupted, dangling containers/images may remain; rerunning with `--clean --cache-level base` forces removal of instance/env layers.

## Common failure modes

* **Patch apply failure**: See `APPLY_PATCH_FAIL` in the instance log. Often caused by outdated base commit or whitespace drift.
* **Missing dependency**: Environment image build fails because repo requirements changed or need extra system packages. Rebuild with `--force_rebuild` or update the dataset’s instructions.
* **Timeout**: Tests exceed the timeout. Increase `--timeout` for heavy repos.
* **Docker daemon not reachable**: Validator fails early; start Docker and ensure the runner user has permission.
* **Regression in PASS_TO_PASS**: The harness explicitly checks PASS_TO_PASS; failing tests are listed under `tests_status.PASS_TO_PASS.failure` in the instance report.

## Tips for local debugging

* Inspect per-instance logs: `logs/run_evaluation/<run_id>/validator/<instance_id>/test_output.txt`.
* Re-run a single instance with `--files data_points/<id>.json --max-workers 1 --force-rebuild`.
* Keep environment images cached (`--cache-level env`) to speed up repeated runs.
* To see the exact Docker build context for an instance, check the symlink `logs/run_evaluation/<run_id>/validator/<instance_id>/image_build_dir`.
