# SWE-bench data point validator

Validate SWE-bench data points locally and in CI using the official evaluation harness. This repository also ships a helper downloader and documents the Docker layering used by the harness so you can reliably reproduce harness behavior.

## What is included
- CLI validator: `swe_bench_validator_custom` turns data point JSON files into the dataset/prediction format expected by the harness and runs the evaluation inside Docker.
- GitHub Action: `.github/workflows/validate-datapoints.yml` validates modified data points on pushes and PRs.
- Downloader: `swe_bench_downloader` fetches SWE-bench instances into `data_points/`.
- Architecture notes: `swe-bench-docker-architecture.md` explains the base → environment → instance Docker image flow and when images rebuild.

## Requirements
- Docker daemon running and accessible to your user (verify with `docker ps`).
- Python 3.12.
- [uv](https://github.com/astral-sh/uv) installed (`python -m pip install uv` works if you do not have the binary).
- Disk space: Docker images for SWE-bench repos can be large; keep several GB free.

## Repository layout
- `data_points/`: sample or downloaded SWE-bench JSON instances.
- `swe_bench_validator_custom/`: validation CLI and harness adapter.
- `swe_bench_downloader/`: downloader CLI and helper utilities.
- `scripts/`: convenience shell wrappers (e.g., `download_swe_bench.sh`).
- `swe-bench-docker-architecture.md`: detailed Docker architecture reference.
- `.github/workflows/validate-datapoints.yml`: CI entrypoint for validation.
- `task.md` / `task-short.md`: task descriptions (for context only).

## Setup
```bash
uv sync --no-dev  # creates .venv and installs dependencies from pyproject.toml/uv.lock
```
All commands below assume you run them from the repo root; prefix with `uv run` to use the virtual environment without activating it.

## Data point format (quick reference)
Each JSON file must provide these fields (see `data_points/*.json` for examples):
- `instance_id`: unique id, e.g., `repo__repo-12345`.
- `repo`: GitHub repo path, e.g., `django/django`.
- `base_commit`: commit hash to check out before applying the patch.
- `patch`: unified diff to apply.
- `FAIL_TO_PASS`: list (or JSON-encoded list) of tests expected to fail before the patch and pass after.
- `PASS_TO_PASS`: list (or JSON-encoded list) of tests expected to stay passing.

The validator normalizes the two test lists and fails fast if required fields are missing.

## Validate data points locally
1) Ensure Docker is running and you can `docker ps`.  
2) Run the validator:
```bash
# Validate every JSON file in data_points/ with a 15 minute timeout
uv run python -m swe_bench_validator_custom.cli --timeout 900

# Validate a subset (glob patterns supported)
uv run python -m swe_bench_validator_custom.cli --files "data_points/astropy__astropy-*.json"
```

Common options:
- `--data-dir DIR`: directory scanned when `--files` is not provided (default: `data_points`).
- `--max-workers N`: harness parallelism (default: 2). Increase gradually to avoid Docker contention.
- `--timeout SECONDS`: per-instance test timeout inside the harness (default: 1200).
- `--cache-level [none|base|env|instance]`: how much of the Docker build cache to reuse (default: `env`).
- `--clean`: drop images above the cache level after the run to reclaim disk space.
- `--force-rebuild`: rebuild everything, bypassing cached images.
- `--namespace NAME` / `--instance-image-tag TAG`: controls Docker image naming; use `--namespace none` to disable namespacing.
- `--run-id ID`: custom identifier for logs/reports; defaults to `validator-<timestamp>`.
- `--workdir PATH`: where temporary dataset/prediction files and run reports are written (default: `.swe-bench-validator`).

Execution flow in detail:
1) Each JSON file is loaded; required fields are checked and test lists are normalized.  
2) Temporary dataset/predictions files are written under `.swe-bench-validator/`.  
3) The SWE-bench harness builds or reuses Docker images (base → environment → instance), applies patches, and runs PASS_TO_PASS/FAIL_TO_PASS tests.  
4) Validation fails if any test fails, a patch cannot be applied, or the harness reports unresolved/error instances.  
5) Run artifacts:
   - Summary report: `.swe-bench-validator/<run_id>.json`
   - Per-instance logs: `logs/run_evaluation/<run_id>/<model>/<instance_id>/`
   - Harness report file: `logs/run_evaluation/<run_id>/<model>/<instance_id>/report.json`

## Download SWE-bench data points
Use the bundled downloader to fetch instances into `data_points/`:
```bash
# Download a specific instance
uv run python -m swe_bench_downloader.cli --instance_id "django__django-12345"

# Grab a handful of issues from a repo
uv run python -m swe_bench_downloader.cli --repo "django/django" --limit 5

# Pull a range from a dataset variant
uv run python -m swe_bench_downloader.cli --dataset "swe-bench-lite" --split test --start_idx 0 --end_idx 20
```
The script `scripts/download_swe_bench.sh` wraps the same CLI if you prefer a shell entrypoint.

Downloader notes:
- `--force` overwrites existing files; omit it to skip already-downloaded instances.
- `--difficulty`, `--start_idx`, `--end_idx`, and `--limit` let you narrow large pulls.
- Output defaults to `data_points/`, but `--output_dir` can target another folder.

## CI workflow
`.github/workflows/validate-datapoints.yml` watches `data_points/**`. When those files change on a branch or PR:
- The workflow installs dependencies with `uv` (no dev extras).
- It detects modified JSON files and runs the validator only against those paths.
- Failures surface as required status checks so broken data points cannot merge.
- Logs and reports are uploaded as artifacts for inspection.

## Tips for faster runs
- Start with `--cache-level env` (default) to reuse base/environment layers; bump to `instance` to reuse more, or set `none` for a clean rebuild.
- Use `--files` to limit validation to the data points you touched.
- If the host is resource-constrained, lower `--max-workers` to reduce simultaneous Docker load.
- Use `--open-file-limit` if you see file descriptor errors on Linux.

## Troubleshooting
- Docker permission errors: ensure your user can run `docker ps` without sudo and that the daemon is running.
- Reusing old images: add `--force-rebuild` or lower `--cache-level` if you suspect stale caches.
- Disk pressure: use `--clean` after a run to remove images above the selected cache level; prune old Docker images/volumes if needed.
- Patch failures: check `logs/run_evaluation/<run_id>/.../report.json` for patch apply errors; confirm the `patch` field matches the target commit.
- Test failures: inspect `tests_status` in per-instance reports to see which PASS_TO_PASS or FAIL_TO_PASS entries failed.
- Missing fields: the validator raises `ValidationError` with the file path and missing field name.

## FAQ
- **Do I need GPU support?** No; the harness runs repository tests inside Docker without GPU requirements.
- **Can I skip Docker?** No; the harness expects to run in Docker to isolate dependencies.
- **Where are temporary files written?** `.swe-bench-validator/` by default; override with `--workdir`.
- **Can I run outside the virtualenv?** Yes, if the dependencies in `pyproject.toml` are globally installed, but `uv run` is recommended to pin versions.

## Contributing / extending
- Add new data points under `data_points/` and validate them locally before opening a PR.
- If you adjust harness options, ensure `.github/workflows/validate-datapoints.yml` stays aligned with defaults or document deviations.
- Keep `swe-bench-docker-architecture.md` in sync if you change image naming or cache behavior.
- Run `uv lock` if you upgrade dependencies; commit both `pyproject.toml` and `uv.lock`.

## Quick reference commands
- Setup: `uv sync --no-dev`
- Validate all: `uv run python -m swe_bench_validator_custom.cli`
- Validate some: `uv run python -m swe_bench_validator_custom.cli --files "data_points/<pattern>.json"`
- Rebuild everything: `uv run python -m swe_bench_validator_custom.cli --force-rebuild --cache-level none`
- Download examples: `uv run python -m swe_bench_downloader.cli --repo "django/django" --limit 5`
