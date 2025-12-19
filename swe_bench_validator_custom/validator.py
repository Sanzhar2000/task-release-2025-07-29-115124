from __future__ import annotations

import json
import logging
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence

import docker
from swebench.harness import run_evaluation
from swebench.harness.constants import (
    FAIL_TO_PASS,
    KEY_INSTANCE_ID,
    KEY_MODEL,
    KEY_PREDICTION,
    LOG_REPORT,
    PASS_TO_PASS,
    RUN_EVALUATION_LOG_DIR,
)

LOG = logging.getLogger(__name__)


@dataclass
class LoadedDatapoint:
    path: Path
    payload: dict

    @property
    def instance_id(self) -> str:
        return self.payload[KEY_INSTANCE_ID]


class ValidationError(Exception):
    """Raised when validation cannot proceed due to structural or execution errors."""


def _parse_test_list(raw_value, field_name: str, path: Path) -> List[str]:
    """
    Normalize PASS_TO_PASS / FAIL_TO_PASS fields to lists.
    The SWE-bench format sometimes stores JSON strings; accept both strings and lists.
    """
    if raw_value is None:
        raise ValidationError(f"{path}: missing required field '{field_name}'")
    if isinstance(raw_value, list):
        return [str(v) for v in raw_value]
    if isinstance(raw_value, str):
        try:
            parsed = json.loads(raw_value)
            if isinstance(parsed, list):
                return [str(v) for v in parsed]
        except json.JSONDecodeError:
            pass
    raise ValidationError(f"{path}: field '{field_name}' must be a list or JSON list string")


def _ensure_required_fields(payload: dict, path: Path) -> None:
    required = ["repo", "base_commit", "patch", KEY_INSTANCE_ID]
    for field in required:
        if not payload.get(field):
            raise ValidationError(f"{path}: missing required field '{field}'")


def load_datapoint(path: Path) -> LoadedDatapoint:
    """Load and validate a single data point JSON file."""
    try:
        payload = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise ValidationError(f"{path}: invalid JSON - {exc}") from exc

    _ensure_required_fields(payload, path)

    payload[FAIL_TO_PASS] = _parse_test_list(payload.get(FAIL_TO_PASS), FAIL_TO_PASS, path)
    payload[PASS_TO_PASS] = _parse_test_list(payload.get(PASS_TO_PASS), PASS_TO_PASS, path)

    return LoadedDatapoint(path=path, payload=payload)


def write_temporary_files(
    datapoints: Sequence[LoadedDatapoint],
    run_id: str,
    workdir: Path,
) -> tuple[Path, Path]:
    """
    Write the dataset and predictions files expected by the SWE-bench harness.
    Returns (dataset_path, predictions_path).
    """
    workdir.mkdir(parents=True, exist_ok=True)
    dataset_path = workdir / f"dataset.{run_id}.json"
    predictions_path = workdir / f"predictions.{run_id}.json"

    dataset_payload = [dp.payload for dp in datapoints]
    predictions_payload = [
        {
            KEY_INSTANCE_ID: dp.instance_id,
            KEY_PREDICTION: dp.payload["patch"],
            KEY_MODEL: "validator",
        }
        for dp in datapoints
    ]

    dataset_path.write_text(json.dumps(dataset_payload, indent=2))
    predictions_path.write_text(json.dumps(predictions_payload, indent=2))
    return dataset_path, predictions_path


def _docker_sanity_check() -> None:
    """
    Ensure Docker daemon is reachable before invoking the harness.
    """
    try:
        client = docker.from_env()
        client.ping()
    except Exception as exc:  # pragma: no cover - defensive guard
        raise ValidationError(
            "Docker is required for SWE-bench validation but is not accessible. "
            "Ensure the Docker daemon is running and the current user has permission."
        ) from exc


def _read_instance_report(run_id: str, model: str, instance_id: str) -> dict | None:
    report_file = RUN_EVALUATION_LOG_DIR / run_id / model.replace("/", "__") / instance_id / LOG_REPORT
    if not report_file.exists():
        return None
    try:
        report = json.loads(report_file.read_text())
        return report.get(instance_id)
    except Exception:  # pragma: no cover - best effort
        return None


def _format_failure_details(instance_ids: Iterable[str], run_id: str, model: str) -> list[str]:
    messages: list[str] = []
    for instance_id in instance_ids:
        report = _read_instance_report(run_id, model, instance_id)
        if not report:
            messages.append(f"{instance_id}: no report produced")
            continue
        tests_status = report.get("tests_status", {})
        failing_f2p = tests_status.get(FAIL_TO_PASS, {}).get("failure", [])
        failing_p2p = tests_status.get(PASS_TO_PASS, {}).get("failure", [])
        details = []
        if failing_f2p:
            details.append(f"FAIL_TO_PASS failed: {', '.join(failing_f2p)}")
        if failing_p2p:
            details.append(f"PASS_TO_PASS failed: {', '.join(failing_p2p)}")
        if not details:
            details.append("see run logs for details")
        messages.append(f"{instance_id}: " + "; ".join(details))
    return messages


def run_validation(
    datapoint_paths: Sequence[Path],
    *,
    timeout: int = 1200,
    max_workers: int = 2,
    cache_level: str = "env",
    clean: bool = False,
    force_rebuild: bool = False,
    namespace: str | None = "swebench",
    instance_image_tag: str = "latest",
    open_file_limit: int = 4096,
    run_id: str | None = None,
    workdir: Path | None = None,
) -> dict:
    """
    Validate the provided data point files using the official SWE-bench harness.
    Returns a summary dictionary; raises ValidationError on failure.
    """
    if not datapoint_paths:
        raise ValidationError("No data point files were provided for validation.")

    _docker_sanity_check()

    resolved_run_id = run_id or f"validator-{int(time.time())}"
    workdir = workdir or Path(".swe-bench-validator")

    datapoints = [load_datapoint(path) for path in datapoint_paths]
    dataset_path, predictions_path = write_temporary_files(datapoints, resolved_run_id, workdir)

    try:
        report_path = run_evaluation.main(
            dataset_name=str(dataset_path),
            split="test",
            instance_ids=[dp.instance_id for dp in datapoints],
            predictions_path=str(predictions_path),
            max_workers=max_workers,
            force_rebuild=force_rebuild,
            cache_level=cache_level,
            clean=clean,
            open_file_limit=open_file_limit,
            run_id=resolved_run_id,
            timeout=timeout,
            namespace=namespace,
            rewrite_reports=False,
            modal=False,
            instance_image_tag=instance_image_tag,
            report_dir=str(workdir),
        )
    except Exception as exc:
        LOG.exception("Validation run failed")
        raise ValidationError(
            f"Failed to run SWE-bench harness for {len(datapoints)} instance(s): {exc}"
        ) from exc

    if not report_path or not Path(report_path).exists():
        raise ValidationError("SWE-bench harness did not produce a run report.")

    run_report = json.loads(Path(report_path).read_text())
    unresolved = set(run_report.get("unresolved_ids", []))
    errors = set(run_report.get("error_ids", []))
    incomplete = set(run_report.get("incomplete_ids", []))
    empty_patch = set(run_report.get("empty_patch_ids", []))

    failures = unresolved | errors | incomplete | empty_patch
    if failures:
        details = _format_failure_details(failures, resolved_run_id, "validator")
        raise ValidationError(
            "One or more instances failed validation:\n" + "\n".join(details)
        )

    return {
        "run_id": resolved_run_id,
        "report_path": str(report_path),
        "resolved_ids": run_report.get("resolved_ids", []),
        "completed_ids": run_report.get("completed_ids", []),
    }
