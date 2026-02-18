import requests
from logging import Logger
from typing import List, Optional

import pyclowder.datasets


def dataset_has_xls_file(
    connector,
    host: str,
    secret_key: str,
    dataset_id: str,
    logger: Optional[Logger] = None,
) -> bool:
    """
    Return True if the dataset already contains an .xls/.xlsx file.

    Uses the `pyclowder` Python SDK to list dataset files via
    `pyclowder.datasets.get_file_list(...)`, then checks for spreadsheet extensions.
    """
    if not dataset_id:
        return False

    try:
        files = pyclowder.datasets.get_file_list(
            connector, host, secret_key, dataset_id
        )
    except Exception as e:
        if logger:
            logger.debug(
                "pyclowder.datasets.get_file_list failed for dataset %s: %s",
                dataset_id,
                e,
            )
        return False

    if not isinstance(files, list):
        return False

    filenames: List[str] = []
    for f in files:
        if not isinstance(f, dict):
            continue
        fname = f.get("filename")
        if not isinstance(fname, str) or not fname:
            continue

        filenames.append(fname)

        if fname.lower().endswith((".xls", ".xlsx")):
            if logger:
                logger.info("Found spreadsheet file in dataset: %s", fname)
            return True

    if logger:
        logger.info("filenames in dataset: %s", filenames)

    return False


def delete_files_from_dataset_by_filename(
    connector,
    host: str,
    secret_key: str,
    dataset_id: str,
    filename: str,
    logger: Optional[Logger] = None,
) -> int:
    """
    Delete all files in a dataset matching the given filename.

    Returns the number of deleted files.
    """
    if not dataset_id or not filename:
        return 0

    try:
        files = pyclowder.datasets.get_file_list(
            connector, host, secret_key, dataset_id
        )
    except Exception as e:
        if logger:
            logger.warning(
                "Failed to list dataset files for deletion check (dataset=%s): %s",
                dataset_id,
                e,
                exc_info=True,
            )
        return 0

    if not isinstance(files, list):
        return 0

    to_delete: List[str] = []
    for f in files:
        if not isinstance(f, dict):
            continue
        if f.get("filename") == filename and f.get("id"):
            to_delete.append(f["id"])

    deleted = 0
    for file_id in to_delete:
        try:
            url = "%sapi/files/%s?key=%s" % (host, file_id, secret_key)
            result = requests.delete(
                url, verify=connector.ssl_verify if connector else True
            )
            result.raise_for_status()
            deleted += 1
            if logger:
                logger.info(
                    "Deleted existing file %s (%s) from dataset %s",
                    filename,
                    file_id,
                    dataset_id,
                )
        except Exception as e:
            if logger:
                logger.warning(
                    "Failed deleting file %s (%s) from dataset %s: %s",
                    filename,
                    file_id,
                    dataset_id,
                    e,
                    exc_info=True,
                )

    return deleted
