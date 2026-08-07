import logging
import re
import shlex
from pathlib import Path
from typing import Any, List

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


def purge_remote(config: dict[str, Any], dry_run: bool = False) -> None:
    """Apply the retention policy on every enabled remote.

    The remotes are written to with rsync but never pruned by it, so without
    this they grow by one full backup per cycle until the disk is full.
    """
    for name, remote in config['remote'].items():
        if not remote['enable']:
            logger.info(f"skipping purge on {name} (disabled)")
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


def purge_one_remote(name: str, remote: dict[str, Any], config: dict[str, Any], dry_run: bool = False) -> None:
    num_full = int(remote.get('num_full_backups', config['general']['num_full_backups']))
    num_diff = int(remote.get('num_differential_backups', config['general']['num_differential_backups']))
    directory = remote_backup_dir(config, remote)
    logger.info(f"purging {name}:{directory} down to {num_full} full and {num_diff} differential backups")

    listing = run_cmd_output(ssh_cmd(remote, f"ls -1 -- {shlex.quote(directory)}"))
    if listing is None:
        logger.error(f"could not list the backups on {name}. Skipping the purge for this remote")
        return

    # The file names start with the creation time, so sorting them in reverse
    # gives newest first without having to stat anything over ssh.
    names = sorted((line.strip() for line in listing.splitlines() if line.strip()), reverse=True)
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
        logger.error(f"the purge would delete every file in {directory} on {name}. Refusing")
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
