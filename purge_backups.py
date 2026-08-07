import logging
import os
from typing import Any, Dict, List

from utils import (
    DIFF_BACKUP_REGEX,
    FULL_BACKUP_REGEX,
    SNAR_REGEX,
    backup_prefix,
    backup_timestamp,
    get_backup_files,
)

logger = logging.getLogger(__name__)


def remove_backup(path: str, reason: str, dry_run: bool = False) -> None:
    if dry_run:
        logger.info(f"DRY RUN: would delete {path} ({reason})")
        return
    logger.info(f"deleting {path} ({reason})")
    os.remove(path)


def group_by_backup(files: List[str]) -> Dict[str, List[str]]:
    """Group file paths by the backup they belong to, newest backup first.

    One backup can be on disk as more than one file -- the plain .tar.gz and its
    .tar.gz.gpg exist side by side until encryption succeeds. Counting files
    instead of backups makes the retention limit fire a cycle early and delete a
    real backup, so every decision below counts groups.
    """
    groups: Dict[str, List[str]] = {}
    for path in files:  # get_backup_files returns newest first
        groups.setdefault(backup_prefix(path), []).append(path)
    return groups


def purge_backups(config: dict[str, Any], dry_run: bool = False) -> None:
    target_dir: str = config['general']['target_dir']
    target_dir = os.path.abspath(target_dir)
    num_full: int = int(config['general']['num_full_backups'])
    num_diff: int = int(config['general']['num_differential_backups'])
    if num_full < 1:
        logger.warning(f"num_full_backups is {num_full}, refusing to keep fewer than one full backup")
        num_full = 1

    # Manage full backups:
    full_backups = group_by_backup(get_backup_files(target_dir, FULL_BACKUP_REGEX))
    kept_full = list(full_backups)[:num_full]

    if num_full >= len(full_backups):
        logger.info(f"only found {len(full_backups)} full backups not removing any")
    else:
        bks_to_remove = list(full_backups)[num_full:]
        logger.debug(f"found the following backups to remove {bks_to_remove}")
        logger.info(f"found {len(bks_to_remove)} backups to remove")
        for name in bks_to_remove:
            for path in full_backups[name]:
                remove_backup(path, f"only the newest {num_full} full backups are kept", dry_run)

    differentials = group_by_backup(get_backup_files(target_dir, DIFF_BACKUP_REGEX))

    # A differential is built from a copy of the .snar of its full backup, so it
    # is cumulative since that full. Once the full is gone the differential
    # cannot be restored any more.
    if kept_full:
        oldest_kept = backup_timestamp(kept_full[-1])
        if oldest_kept is not None:
            still_useful: List[str] = []
            for name in differentials:
                stamp = backup_timestamp(name)
                if stamp is not None and stamp < oldest_kept:
                    for path in differentials[name]:
                        remove_backup(path, "older than the oldest kept full backup", dry_run)
                else:
                    still_useful.append(name)
            differentials = {name: differentials[name] for name in still_useful}

    # Of the remaining differentials keep only the newest num_diff many.
    if num_diff >= len(differentials):
        logger.info(f"only found {len(differentials)} differential backups not removing any")
    else:
        for name in list(differentials)[num_diff:]:
            for path in differentials[name]:
                remove_backup(path, f"only the newest {num_diff} differential backups are kept", dry_run)

    purge_snar_files(target_dir, kept_full, dry_run)


def purge_snar_files(target_dir: str, kept_full: List[str], dry_run: bool = False) -> None:
    """Drop the tar snapshot files of full backups that no longer exist.

    Only the newest full backup's .snar is ever read (to build the next
    differential) and that backup is always among the kept ones, so this never
    removes a file the next run needs.
    """
    if not kept_full:
        logger.info("no full backups present, leaving the .snar files alone")
        return

    kept_prefixes = set(kept_full)
    orphans = [
        snar for snar in get_backup_files(target_dir, SNAR_REGEX)
        if backup_prefix(snar) not in kept_prefixes
    ]
    if not orphans:
        logger.info("no orphaned .snar files found")
        return

    logger.info(f"found {len(orphans)} orphaned .snar files to remove")
    for snar in orphans:
        remove_backup(snar, "no matching full backup", dry_run)
