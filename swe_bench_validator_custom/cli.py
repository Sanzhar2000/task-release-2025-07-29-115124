from __future__ import annotations

import glob
import logging
import sys
from pathlib import Path
from typing import List, Sequence

import click

from .validator import ValidationError, run_validation


def _collect_paths(files: Sequence[str], data_dir: str) -> List[Path]:
    if files:
        return [Path(f) for pattern in files for f in glob.glob(pattern)]
    return [Path(p) for p in sorted(Path(data_dir).glob("*.json"))]


@click.command()
@click.option(
    "--files",
    "-f",
    multiple=True,
    help="Specific data point files or glob patterns to validate (default: all in data_points/).",
)
@click.option(
    "--data-dir",
    default="data_points",
    show_default=True,
    help="Directory to scan when no --files are provided.",
)
@click.option(
    "--timeout",
    default=1200,
    show_default=True,
    help="Timeout (seconds) for each instance test run inside the harness.",
)
@click.option(
    "--max-workers",
    default=2,
    show_default=True,
    help="Maximum parallel workers for harness execution.",
)
@click.option(
    "--cache-level",
    default="env",
    show_default=True,
    type=click.Choice(["none", "base", "env", "instance"]),
    help="Harness cache level for Docker images.",
)
@click.option(
    "--clean",
    is_flag=True,
    default=False,
    help="Remove images above the cache level after the run.",
)
@click.option(
    "--force-rebuild",
    is_flag=True,
    default=False,
    help="Force rebuild all images (disables cache reuse).",
)
@click.option(
    "--namespace",
    default="swebench",
    show_default=True,
    help='Docker namespace; use "none" to disable namespacing.',
)
@click.option(
    "--instance-image-tag",
    default="latest",
    show_default=True,
    help="Tag used for instance images built by the harness.",
)
@click.option(
    "--open-file-limit",
    default=4096,
    show_default=True,
    help="File descriptor limit for the harness (Linux only).",
)
@click.option(
    "--run-id",
    help="Optional run identifier; defaults to a timestamped value.",
)
@click.option(
    "--workdir",
    default=".swe-bench-validator",
    show_default=True,
    help="Directory where temporary dataset/prediction files and reports are written.",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Enable verbose logging.",
)
def main(
    files: Sequence[str],
    data_dir: str,
    timeout: int,
    max_workers: int,
    cache_level: str,
    clean: bool,
    force_rebuild: bool,
    namespace: str | None,
    instance_image_tag: str,
    open_file_limit: int,
    run_id: str | None,
    workdir: str,
    verbose: bool,
):
    """
    Validate SWE-bench data point JSON files using the official harness.
    """
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )
    paths = _collect_paths(files, data_dir)
    if not paths:
        click.echo("No data point files found to validate.", err=True)
        sys.exit(1)
    print(f"paths: {paths}")
    try:
        summary = run_validation(
            [Path(p) for p in paths],
            timeout=timeout,
            max_workers=max_workers,
            cache_level=cache_level,
            clean=clean,
            force_rebuild=force_rebuild,
            namespace=None if namespace == "none" else namespace,
            instance_image_tag=instance_image_tag,
            open_file_limit=open_file_limit,
            run_id=run_id,
            workdir=Path(workdir),
        )
    except ValidationError as exc:
        click.echo(str(exc), err=True)
        sys.exit(1)

    click.echo(
        f"Validation succeeded for {len(summary['resolved_ids'])} instance(s). "
        f"Run report: {summary['report_path']}"
    )


if __name__ == "__main__":
    main()
