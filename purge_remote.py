import logging
import os
import re
import shlex
from pathlib import Path
from typing import Any, Dict, List, Optional

from utils import (
    DIFF_BACKUP_REGEX,
    FULL_BACKUP_REGEX,
    SNAR_REGEX,
    backup_prefix,
    backup_timestamp,
    run_cmd,
    run_cmd_output,
)

logger = logging.getLogger(__name__)


def purge_remote(
    config: dict[str, Any],
    sync_results: Optional[dict[str, bool]] = None,
    dry_run: bool = False,
) -> None:
    """Apply the retention policy on every enabled remote.

    The remotes are written to with rsync but never pruned by it, so without
    this they grow by one full backup per cycle until the disk is full.

    sync_results comes from remote_backup: a remote whose copy failed this run
    is skipped, because rsync writes with --append --inplace and a failed
    transfer leaves a truncated file under the final name.
    """
    for name, remote in config['remote'].items():
        if not remote['enable']:
            logger.info(f"skipping purge on {name} (disabled)")
            continue
        if sync_results is not None and not sync_results.get(name, False):
            logger.warning(f"skipping purge on {name}: the copy to it did not succeed this run")
            continue
        purge_one_remote(name, remote, config, dry_run)


def remote_backup_dir(config: dict[str, Any], remote: dict[str, Any]) -> str:
    """Directory the backups actually live in on the remote.

    remote_backup() rsyncs the target dir itself and not its contents (no
    trailing slash), so everything ends up one level below the configured
    target_dir, e.g. /mnt/cloud_backup/restore_points/cloud_backup.
    """
    local_name = Path(config['general']['target_dir']).absolute().name
    return remote['target_dir'].rstrip('/') + '/' + local_name


def ssh_cmd(remote: dict[str, Any], remote_command: str) -> List[str]:
    """Build an ssh invocation using the same credentials as the rsync."""
    cmd: List[str] = []
    if remote.get('run_as'):
        cmd += ["sudo", "-u", remote['run_as']]
    cmd += ["ssh"]
    if remote.get('ssh_key'):
        cmd += ["-i", remote['ssh_key']]
    cmd += [f"{remote['username']}@{remote['address']}", remote_command]
    return cmd


def list_remote_files(remote: dict[str, Any], directory: str) -> Optional[Dict[str, int]]:
    """Map file name -> size for the remote backup dir, None if it cannot be listed."""
    listing = run_cmd_output(ssh_cmd(remote, f"find {shlex.quote(directory)} -maxdepth 1 -type f -printf '%s %f\\n'"))
    if listing is None:
        return None
    files: Dict[str, int] = {}
    for line in listing.splitlines():
        line = line.strip()
        if not line:
            continue
        size, _, name = line.partition(" ")
        try:
            files[name] = int(size)
        except ValueError:
            logger.warning(f"could not read the size of {name!r} from the remote listing, ignoring it")
    return files


def local_file_sizes(target_dir: str) -> Dict[str, int]:
    sizes: Dict[str, int] = {}
    for entry in os.scandir(target_dir):
        if entry.is_file():
            sizes[entry.name] = entry.stat().st_size
    return sizes


def retention_limits(remote: dict[str, Any], config: dict[str, Any]) -> tuple[int, int]:
    """Per-remote retention, never below the local one.

    The rsync has no --delete and the local copies stay, so anything deleted
    here that still exists locally is simply re-uploaded on the next run and
    deleted again -- forever, at one full backup per night.
    """
    limits = []
    for key in ('num_full_backups', 'num_differential_backups'):
        local = int(config['general'][key])
        value = int(remote.get(key, local))
        if key == 'num_full_backups' and value < 1:
            logger.warning(f"num_full_backups is {value}, refusing to keep fewer than one full backup")
            value = 1
        if value < local:
            logger.warning(
                f"{key} is {value} for this remote but {local} locally. Using {local}: a smaller "
                f"remote value only makes the next rsync upload the deleted backups again"
            )
            value = local
        limits.append(value)
    return limits[0], limits[1]


def purge_one_remote(name: str, remote: dict[str, Any], config: dict[str, Any], dry_run: bool = False) -> None:
    num_full, num_diff = retention_limits(remote, config)
    directory = remote_backup_dir(config, remote)
    logger.info(f"purging {name}:{directory} down to {num_full} full and {num_diff} differential backups")

    remote_files = list_remote_files(remote, directory)
    if remote_files is None:
        logger.error(f"could not list the backups on {name}. Skipping the purge for this remote")
        return

    # A file whose size does not match the local copy was cut short in transit.
    # It is neither counted towards the retention limit (so it cannot evict a
    # good backup) nor deleted (so --append can still finish it).
    local_sizes = local_file_sizes(os.path.abspath(config['general']['target_dir']))
    incomplete = {n for n, size in remote_files.items() if n in local_sizes and local_sizes[n] != size}
    if incomplete:
        logger.warning(
            f"{len(incomplete)} file(s) on {name} do not match their local size and are being ignored, "
            f"they were most likely cut short in transit: {sorted(incomplete)}"
        )

    names = sorted((n for n in remote_files if n not in incomplete), reverse=True)
    fulls = [n for n in names if re.search(FULL_BACKUP_REGEX, n)]
    diffs = [n for n in names if re.search(DIFF_BACKUP_REGEX, n)]
    snars = [n for n in names if re.search(SNAR_REGEX, n)]
    logger.info(f"{name} holds {len(fulls)} full, {len(diffs)} differential backups and {len(snars)} snar files")

    if not fulls:
        logger.error(f"no full backups found in {directory} on {name}. Refusing to delete anything")
        return

    kept_full = fulls[:num_full]
    kept_prefixes = {backup_prefix(bk) for bk in kept_full}
    oldest_kept = backup_timestamp(kept_full[-1])

    to_delete = list(fulls[num_full:])
    kept_diffs: List[str] = []
    for bk in diffs:
        stamp = backup_timestamp(bk)
        if oldest_kept is not None and stamp is not None and stamp < oldest_kept:
            to_delete.append(bk)  # its full backup is gone, cannot be restored
        else:
            kept_diffs.append(bk)
    to_delete += kept_diffs[num_diff:]
    to_delete += [s for s in snars if backup_prefix(s) not in kept_prefixes]

    if not to_delete:
        logger.info(f"nothing to purge on {name}")
        return
    if len(to_delete) >= len(names):
        logger.error(f"the purge would delete every backup in {directory} on {name}. Refusing")
        return

    paths = [f"{directory}/{n}" for n in to_delete]
    if dry_run:
        logger.info(f"DRY RUN: would delete {len(paths)} files on {name}:")
        for path in paths:
            logger.info(f"DRY RUN:   {path}")
        logger.info(f"DRY RUN: would keep {len(kept_full)} full and {min(len(kept_diffs), num_diff)} differential backups on {name}")
        return

    logger.info(f"deleting {len(paths)} files on {name}")
    # Explicit paths only, never a glob, so a bad pattern cannot widen the delete.
    rm_cmd = "rm -f -- " + " ".join(shlex.quote(path) for path in paths)
    if run_cmd(ssh_cmd(remote, rm_cmd)):
        logger.info(f"purged {len(paths)} files on {name}")
    else:
        logger.error(f"purge failed on {name}")
