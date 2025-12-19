#!/bin/bash

# SWE-bench Data Downloader
# Downloads SWE-bench data points using the official SWE-bench library
# Usage: ./scripts/download_swe_bench.sh [options]

set -e

# Change to the project root directory
cd "$(dirname "$0")/.."

# Use UV to run the Python module with all arguments passed through
uv run python -m swe_bench_downloader "$@" 