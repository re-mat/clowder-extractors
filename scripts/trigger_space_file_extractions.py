"""Trigger a specific extractor for matching files across all datasets in a space.

This script is designed for one-off / batch orchestration tasks.
It uses `pyclowder` wherever possible and falls back to direct API calls for
endpoints that are not wrapped by the SDK.
To run:
PYTHONPATH=src ./venv/bin/python scripts/trigger_space_file_extractions.py --host "http://localhost:8000/" --api-key "217ae198-a352-4d2d-9c9a-9ef4c9320ab4" --space-id "69956039e4b0e287e29a07c8" --extractor "remat.parameters.from_txt" --extensions .txt --verbose
"""

from __future__ import annotations

import argparse
import json
import logging
from typing import Any, Iterable, List, Sequence

from pyclowder.client import ClowderClient


LOGGER = logging.getLogger(__name__)


def configure_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def normalize_host(host: str) -> tuple[str, str]:
    """Return host with and without trailing slash."""
    host_without_slash = host.rstrip("/")
    host_with_slash = f"{host_without_slash}/"
    return host_with_slash, host_without_slash


def normalize_extensions(exts: Sequence[str]) -> List[str]:
    normalized = []
    for ext in exts:
        ext = ext.strip().lower()
        if not ext:
            continue
        if not ext.startswith("."):
            ext = f".{ext}"
        normalized.append(ext)
    return normalized


def parse_spaces_datasets_response(payload) -> List[str]:
    """Handle varying payload shapes from /spaces/{id}/datasets."""
    dataset_ids: List[str] = []

    if isinstance(payload, list):
        for item in payload:
            if isinstance(item, str):
                dataset_ids.append(item)
            elif isinstance(item, dict):
                dataset_id = item.get("id")
                if isinstance(dataset_id, str):
                    dataset_ids.append(dataset_id)
    elif isinstance(payload, dict):
        for key in ("datasets", "data", "results"):
            value = payload.get(key)
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, str):
                        dataset_ids.append(item)
                    elif isinstance(item, dict) and isinstance(item.get("id"), str):
                        dataset_ids.append(item["id"])
                break

    return list(dict.fromkeys(dataset_ids))


def list_dataset_ids_in_space(
    client: ClowderClient,
    space_id: str,
    limit: int | None = None,
) -> List[str]:
    params = {}
    if limit is not None:
        params["limit"] = limit

    payload = client.get(f"/spaces/{space_id}/datasets", params=params)
    dataset_ids = parse_spaces_datasets_response(payload)
    return dataset_ids


def file_matches_extensions(filename: str, extensions: Iterable[str]) -> bool:
    filename_lower = filename.lower()
    return any(filename_lower.endswith(ext) for ext in extensions)


def parse_dataset_files_response(payload: Any) -> List[dict]:
    """Handle varying payload shapes from dataset files endpoint."""
    files: List[dict] = []

    if isinstance(payload, list):
        files = [item for item in payload if isinstance(item, dict)]
    elif isinstance(payload, dict):
        for key in ("files", "data", "results"):
            value = payload.get(key)
            if isinstance(value, list):
                files = [item for item in value if isinstance(item, dict)]
                break

    return files


def get_file_identity(file_info: dict) -> tuple[str | None, str | None]:
    """Return (file_id, filename) for different key conventions."""
    file_id = file_info.get("id")
    if not isinstance(file_id, str):
        file_id = file_info.get("_id")
    if isinstance(file_id, dict):
        # Some APIs return {"$oid": "..."}
        oid = file_id.get("$oid")
        file_id = oid if isinstance(oid, str) else None
    if not isinstance(file_id, str):
        file_id = None

    filename = file_info.get("filename")
    if not isinstance(filename, str):
        filename = file_info.get("name")
    if not isinstance(filename, str):
        filename = None

    return file_id, filename


def list_files_in_dataset(client: ClowderClient, dataset_id: str) -> List[dict]:
    """List files in a dataset using pyclowder client."""
    payload = client.get(f"/datasets/{dataset_id}/files")
    files = parse_dataset_files_response(payload)
    if not files and payload:
        LOGGER.warning(
            "Unexpected file list response for dataset %s: %r", dataset_id, payload
        )
    return files


def submit_file_extraction_with_status(
    client: ClowderClient,
    file_id: str,
    extractor_name_or_id: str,
) -> None:
    response = client.post(
        f"/files/{file_id}/extractions",
        {"extractor": extractor_name_or_id},
    )
    LOGGER.debug("Extraction submit response for file %s: %s", file_id, response)


def process_space(
    host: str,
    api_key: str,
    space_id: str,
    extractor_name_or_id: str,
    extensions: Sequence[str],
    ssl_verify: bool = True,
    dry_run: bool = False,
    limit: int | None = None,
) -> dict:
    _sdk_host, client_host = normalize_host(host)
    client = ClowderClient(host=client_host, key=api_key, ssl=ssl_verify)

    dataset_ids = list_dataset_ids_in_space(
        client=client, space_id=space_id, limit=limit
    )
    LOGGER.info("Found %d datasets in space %s", len(dataset_ids), space_id)

    totals = {
        "datasets": len(dataset_ids),
        "files_scanned": 0,
        "files_matched": 0,
        "extractions_submitted": 0,
        "errors": 0,
        "failed_file_ids": [],
    }

    for dataset_id in dataset_ids:
        try:
            files = list_files_in_dataset(client=client, dataset_id=dataset_id)
        except Exception as exc:
            totals["errors"] += 1
            LOGGER.exception(
                "Failed listing files for dataset %s: %s",
                dataset_id,
                exc,
            )
            continue

        LOGGER.debug("Dataset %s has %d files", dataset_id, len(files))

        for file_info in files:
            totals["files_scanned"] += 1

            file_id, filename = get_file_identity(file_info)
            if not file_id or not filename:
                continue

            if not file_matches_extensions(filename, extensions):
                continue

            totals["files_matched"] += 1
            LOGGER.debug(
                "Matched file `%s` (%s) in dataset %s",
                filename,
                file_id,
                dataset_id,
            )

            if dry_run:
                LOGGER.debug(
                    "Dry run: would submit extractor `%s` for file %s",
                    extractor_name_or_id,
                    file_id,
                )
                continue

            try:
                submit_file_extraction_with_status(
                    client=client,
                    file_id=file_id,
                    extractor_name_or_id=extractor_name_or_id,
                )
                totals["extractions_submitted"] += 1
            except Exception as exc:
                totals["errors"] += 1
                totals["failed_file_ids"].append(file_id)
                LOGGER.exception(
                    "Failed submitting extractor `%s` for file %s (%s): %s",
                    extractor_name_or_id,
                    file_id,
                    filename,
                    exc,
                )

    failed_ids = totals["failed_file_ids"]
    if failed_ids:
        unique_failed_ids = list(dict.fromkeys(failed_ids))
        totals["failed_file_ids"] = unique_failed_ids
        LOGGER.error(
            "Failed to submit extractor for %d file(s). File IDs: %s",
            len(unique_failed_ids),
            unique_failed_ids,
        )

    return totals


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Submit file extractor across all matching files in all datasets of a space."
    )
    parser.add_argument(
        "--host",
        required=True,
        help="Clowder host, e.g. https://re-mat.clowder.ncsa.illinois.edu",
    )
    parser.add_argument("--api-key", required=True, help="Clowder API key")
    parser.add_argument("--space-id", required=True, help="Clowder space ID to scan")
    parser.add_argument(
        "--extractor",
        required=True,
        help="Extractor name or ID to submit (e.g. parameter-extractor id)",
    )
    parser.add_argument(
        "--extensions",
        nargs="+",
        default=[".txt"],
        help="File extension(s) to match, e.g. .txt .xlsx (default: .txt)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional limit for /spaces/{id}/datasets endpoint pagination size.",
    )
    parser.add_argument(
        "--insecure",
        action="store_true",
        help="Disable SSL certificate verification.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Log actions without submitting any extraction requests.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug logging.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    configure_logging(verbose=args.verbose)
    extensions = normalize_extensions(args.extensions)
    if not extensions:
        parser.error("At least one valid file extension is required.")

    totals = process_space(
        host=args.host,
        api_key=args.api_key,
        space_id=args.space_id,
        extractor_name_or_id=args.extractor,
        extensions=extensions,
        ssl_verify=not args.insecure,
        dry_run=args.dry_run,
        limit=args.limit,
    )

    LOGGER.info("Completed run summary:\n%s", json.dumps(totals, indent=2))
    return 0 if totals["errors"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
