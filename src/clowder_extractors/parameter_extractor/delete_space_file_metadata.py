"""Back up and delete dataset metadata for every dataset in a space.

This script is intentionally safety-first:
1) It scans all datasets in the target space.
2) It asks for an explicit terminal confirmation before deleting anything.
3) It downloads metadata backups to disk before each delete request.
To run:
PYTHONPATH=src ./venv/bin/python src/clowder_extractors/parameter_extractor/delete_space_file_metadata.py --host "http://localhost:8000/" \
  --api-key "YOUR_API_KEY" \
  --space-id "YOUR_SPACE_ID" \
  --verbose
"""

from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, List

from pyclowder.client import ClowderClient
from pyclowder import datasets as clowder_datasets


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


def parse_spaces_datasets_response(payload: Any) -> List[str]:
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
    return parse_spaces_datasets_response(payload)


def fetch_dataset_metadata(
    connector: SimpleNamespace,
    host_with_slash: str,
    api_key: str,
    dataset_id: str,
    extractor: str | None = None,
) -> Any:
    return clowder_datasets.download_metadata(
        connector=connector,
        host=host_with_slash,
        key=api_key,
        datasetid=dataset_id,
        extractor=extractor,
    )


def remove_dataset_metadata(
    connector: SimpleNamespace,
    host_with_slash: str,
    api_key: str,
    dataset_id: str,
    extractor: str | None = None,
) -> None:
    clowder_datasets.remove_metadata(
        connector=connector,
        host=host_with_slash,
        key=api_key,
        datasetid=dataset_id,
        extractor=extractor,
    )


def sanitize_for_filename(value: str) -> str:
    allowed = []
    for char in value:
        if char.isalnum() or char in ("-", "_", "."):
            allowed.append(char)
        else:
            allowed.append("_")
    return "".join(allowed)[:120]


def backup_metadata(
    backup_root: Path,
    space_id: str,
    dataset_id: str,
    metadata: Any,
) -> Path:
    dataset_dir = backup_root / sanitize_for_filename(dataset_id)
    dataset_dir.mkdir(parents=True, exist_ok=True)

    backup_path = dataset_dir / f"{sanitize_for_filename(dataset_id)}.json"

    payload = {
        "space_id": space_id,
        "dataset_id": dataset_id,
        "saved_at_utc": datetime.now(timezone.utc).isoformat(),
        "metadata": metadata,
    }
    backup_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return backup_path


def collect_space_datasets(
    client: ClowderClient,
    space_id: str,
    limit: int | None = None,
) -> List[str]:
    dataset_ids = list_dataset_ids_in_space(
        client=client, space_id=space_id, limit=limit
    )
    LOGGER.info("Found %d datasets in space %s", len(dataset_ids), space_id)
    return dataset_ids


def prompt_for_confirmation(
    *,
    host: str,
    space_id: str,
    extractor: str | None,
    backup_dir: Path,
    datasets_count: int,
    dry_run: bool,
) -> bool:
    print("\nAbout to process dataset metadata deletion with backup.")
    print(f"Host: {host}")
    print(f"Space ID: {space_id}")
    print(f"Datasets targeted: {datasets_count}")
    print(f"Extractor filter: {extractor if extractor else 'ALL metadata'}")
    print(f"Backup directory: {backup_dir}")
    print(f"Mode: {'DRY RUN (no deletion)' if dry_run else 'DELETE after backup'}")
    print("\nType DELETE to continue, or anything else to cancel: ", end="", flush=True)
    user_input = input().strip()
    return user_input == "DELETE"


def process_space(
    host: str,
    api_key: str,
    space_id: str,
    backup_dir: Path,
    ssl_verify: bool = True,
    extractor: str | None = None,
    dry_run: bool = False,
    limit: int | None = None,
) -> dict:
    host_with_slash, client_host = normalize_host(host)
    client = ClowderClient(host=client_host, key=api_key, ssl=ssl_verify)
    connector = SimpleNamespace(ssl_verify=ssl_verify)

    datasets_to_process = collect_space_datasets(
        client=client, space_id=space_id, limit=limit
    )
    backup_dir.mkdir(parents=True, exist_ok=True)

    totals = {
        "datasets_seen": len(datasets_to_process),
        "metadata_backed_up": 0,
        "metadata_deleted": 0,
        "errors": 0,
        "failed_download_ids": [],
        "failed_delete_ids": [],
        "backup_dir": str(backup_dir),
        "extractor_filter": extractor,
        "dry_run": dry_run,
    }

    if not prompt_for_confirmation(
        host=host_with_slash,
        space_id=space_id,
        extractor=extractor,
        backup_dir=backup_dir,
        datasets_count=len(datasets_to_process),
        dry_run=dry_run,
    ):
        LOGGER.warning("User cancelled operation. No metadata deleted.")
        totals["cancelled"] = True
        return totals

    for dataset_id in datasets_to_process:
        try:
            metadata = fetch_dataset_metadata(
                connector=connector,
                host_with_slash=host_with_slash,
                api_key=api_key,
                dataset_id=dataset_id,
                extractor=extractor,
            )
            backup_path = backup_metadata(
                backup_root=backup_dir,
                space_id=space_id,
                dataset_id=dataset_id,
                metadata=metadata,
            )
            totals["metadata_backed_up"] += 1
            LOGGER.debug(
                "Backed up metadata for dataset %s to %s", dataset_id, backup_path
            )
        except Exception as exc:
            totals["errors"] += 1
            totals["failed_download_ids"].append(dataset_id)
            LOGGER.exception(
                "Failed downloading/backup metadata for dataset %s: %s",
                dataset_id,
                exc,
            )
            # Continue with the next dataset; one failure must not stop the batch.
            continue

        if dry_run:
            continue

        try:
            remove_dataset_metadata(
                connector=connector,
                host_with_slash=host_with_slash,
                api_key=api_key,
                dataset_id=dataset_id,
                extractor=extractor,
            )
            totals["metadata_deleted"] += 1
        except Exception as exc:
            totals["errors"] += 1
            totals["failed_delete_ids"].append(dataset_id)
            LOGGER.exception(
                "Failed deleting metadata for dataset %s: %s",
                dataset_id,
                exc,
            )

    if totals["failed_download_ids"]:
        totals["failed_download_ids"] = list(
            dict.fromkeys(totals["failed_download_ids"])
        )
        LOGGER.error(
            "Metadata download/backup failed for dataset IDs: %s",
            totals["failed_download_ids"],
        )

    if totals["failed_delete_ids"]:
        totals["failed_delete_ids"] = list(dict.fromkeys(totals["failed_delete_ids"]))
        LOGGER.error(
            "Metadata deletion failed for dataset IDs: %s", totals["failed_delete_ids"]
        )

    return totals


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=("Back up and then delete metadata for all datasets in a space.")
    )
    parser.add_argument(
        "--host",
        required=True,
        help="Clowder host, e.g. https://re-mat.clowder.ncsa.illinois.edu",
    )
    parser.add_argument("--api-key", required=True, help="Clowder API key")
    parser.add_argument("--space-id", required=True, help="Clowder space ID to scan")
    parser.add_argument(
        "--backup-dir",
        default=None,
        help=(
            "Directory where metadata backups are saved. "
            "Default: metadata-backups/<space-id>/<UTC timestamp>/"
        ),
    )
    parser.add_argument(
        "--extractor",
        default=None,
        help=(
            "Optional extractor name to restrict backup/deletion. "
            "If omitted, all metadata for each dataset is deleted."
        ),
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
        help="Back up metadata and prompt for confirmation, but skip delete calls.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug logging.",
    )
    return parser


def build_default_backup_dir(space_id: str) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return Path("metadata-backups") / sanitize_for_filename(space_id) / timestamp


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    configure_logging(verbose=args.verbose)
    backup_dir = (
        Path(args.backup_dir)
        if args.backup_dir
        else build_default_backup_dir(args.space_id)
    )

    totals = process_space(
        host=args.host,
        api_key=args.api_key,
        space_id=args.space_id,
        backup_dir=backup_dir,
        ssl_verify=not args.insecure,
        extractor=args.extractor,
        dry_run=args.dry_run,
        limit=args.limit,
    )
    LOGGER.info("Completed run summary:\n%s", json.dumps(totals, indent=2))
    if totals.get("cancelled"):
        return 1
    return 0 if totals["errors"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
