import logging
import subprocess
import time
from os import path as path
import os
import datetime
import shutil
from typing import Any

from utils import (
    ANY_BACKUP_REGEX,
    FULL_BACKUP_REGEX,
    SNAR_REGEX,
    get_backup_files,
    get_docker_prepend,
    get_newest_file_age,
    redact,
    run_cmd,
)

logger = logging.getLogger(__name__)

# Buffers so a cron run that fires slightly early still counts as due.
# They are added to the measured age, never subtracted from it -- subtracting
# would stretch every configured interval (a 7 day full became an 8 day one).
FULL_AGE_BUFFER = 0.5   # half a day for the full backup
DIFF_AGE_BUFFER = 0.2   # only a tenth of a day for the differential


class MaintenanceEnableError(Exception):
    """Maintenance mode could not be enabled, no backup was attempted."""


class BackupCopyError(Exception):
    """Copying the data failed. Maintenance mode was disabled again."""


class MaintenanceDisableError(Exception):
    """Maintenance mode could not be disabled -- Nextcloud is still offline."""


class BackupCreateError(Exception):
    """Writing the archive failed. Any partial file has been removed."""


def discard_partial(file_path: str) -> None:
    """Remove a half-written file, tolerating it not being there."""
    try:
        os.remove(file_path)
        logger.info(f"removed the unusable {file_path}")
    except FileNotFoundError:
        pass
    except OSError as e:
        logger.error(f"could not remove {file_path}: {e}. Remove it by hand before the next run")


def create_backup(config: dict[str, Any]) -> str:
    """
    This function is the top-level function for creating the backup
    it will read the config and determine what if/what kind of backup
    needs to be created and create those backups.
    """
    source_dir: str = config['general']['source_dir']
    target_dir: str = config['general']['target_dir']
    tmp_dir: str    = config['general']['tmp_dir']
    source_dir = path.abspath(source_dir)
    target_dir = path.abspath(target_dir)
    tmp_dir    = path.abspath(tmp_dir)

    assert path.exists(source_dir)
    if not path.exists(target_dir):
        logger.warning("target dir does not exist it will be created please check the target_dir path")
        os.mkdir(target_dir)

    if not path.exists(tmp_dir):
        logger.warning("tmp dir does not exist it will be created please check the tmp_dir path")
        os.mkdir(tmp_dir)

    d_bt_backups: int = config['general']['days_between_backups']
    d_bt_diff_backups: int = config['general']['days_between_diff_backups']

    full_bak_mtime = get_newest_file_age(target_dir, FULL_BACKUP_REGEX)
    full_bak_age = (time.time() - full_bak_mtime) / (60*60*24)
    diff_bak_mtime = get_newest_file_age(target_dir, ANY_BACKUP_REGEX)
    diff_bak_age = (time.time() - diff_bak_mtime) / (60*60*24)
    logger.debug(f"newest File found in full backup folder is {full_bak_age} days old, newest differential is {diff_bak_age}")
    full_bak_age += FULL_AGE_BUFFER
    diff_bak_age += DIFF_AGE_BUFFER

    if full_bak_age < float(d_bt_backups) and diff_bak_age < float(d_bt_diff_backups):
        logger.info(f"Newest File found only {full_bak_age}/{diff_bak_age} days old specified age: {d_bt_backups}/{d_bt_diff_backups}. Skipping backup creation...")
        return "None"

    # Enable maintance mode then copy all files:
    logger.info("Creating new backup")
    maintance_cmd: list[str] = config['general']['maintance_cmd'].split(" ")
    maintenance_enabled = False
    try:
        # TODO: Change to use docker occ
        suc = run_cmd(maintance_cmd + ["--on"])
        if not suc:
            logger.error("Could not enable maintance mode. No backup was created. Please check the command in the config")
            raise MaintenanceEnableError("Failed to enter maintance")
        maintenance_enabled = True
        logger.info("Enabled Maintance Mode")
        prepend: list[str] = []
        if 'docker' in config and config['docker']['enable']:
            prepend = get_docker_prepend(config['docker'], container_name=config['docker']['db_container_name'])
            logger.debug(f"using docker prepend is: {prepend}")

        db_backup_path = path.join(tmp_dir, "database_backup.bak")
        suc = create_db_backup(config['database'], db_backup_path, pre_prend=prepend)
        if not suc:
            logger.error("Failed to create backup of the database. Will continue backing up data")
        else:
            logger.info(f"Created DB backup at {db_backup_path}")
        # Copy files to tmp dir using rsync
        rsync_cmd = ["rsync", "-av", "--delete", source_dir, tmp_dir]
        logger.debug(f"Copying source folder: {source_dir} to tmp dir {tmp_dir} using command: {' '.join(rsync_cmd)}")
        suc = run_cmd(rsync_cmd)
        if not suc:
            logger.error("rsync command failed.")
            raise BackupCopyError("Failed to copy files")
        logger.debug("Copy done")
    finally:
        # Only touch maintenance mode if we actually turned it on. Disabling
        # unconditionally meant a failure to *enable* was replaced by a
        # MaintenanceDisableError from here, which reports Nextcloud as offline
        # when it was never taken offline.
        if maintenance_enabled:
            tries = 0
            disable_suc = False
            while tries < 10 and not disable_suc:
                disable_suc = run_cmd(maintance_cmd + ["--off"])
                tries += 1
            if not disable_suc:
                logger.error("Could not disable maintance mode manual intervention required")
                raise MaintenanceDisableError("failed to disable maintance mode")

    logger.info("Done with Maintance. Compressing backup to final location")

    backup_type: str
    if full_bak_age >= float(d_bt_backups):
        backup_type = "Full"
        logger.info("creating full backup")
        new_backup_name = datetime.datetime.now().strftime("%Y-%m-%d-%H") + '-full'
        new_backup_loc = path.join(target_dir, new_backup_name + ".tar.gz")
        incremental_list = path.join(target_dir, new_backup_name + ".snar")
        compression_cmd: list[str] = ["tar", "-C", tmp_dir, '--use-compress-program="/usr/bin/pigz"',  "-cf", new_backup_loc, "--listed-incremental", incremental_list, "."]
        logger.debug(f"compressions command {' '.join(compression_cmd)}")
        if not run_cmd(compression_cmd):
            # Both files are unusable now, and leaving them behind is worse than
            # having no backup: the truncated archive would be counted as a
            # restore point and evict a good one, and every later differential
            # would be built on top of this .snar.
            discard_partial(new_backup_loc)
            discard_partial(incremental_list)
            raise BackupCreateError("tar failed to create the full backup")

    elif diff_bak_age >= float(d_bt_diff_backups):
        backup_type = "Diff"
        logger.info("creating differential backup")
        newest_incremental: str = get_backup_files(target_dir, SNAR_REGEX)[0]
        shutil.copy(newest_incremental, newest_incremental + ".copy")

        new_backup_name = datetime.datetime.now().strftime("%Y-%m-%d-%H") + '-differential'
        new_backup_loc = path.join(target_dir, new_backup_name + ".tar.gz")
        compression_cmd = ["tar", "-C", tmp_dir, '--use-compress-program="/usr/bin/pigz"',  "-cf", new_backup_loc, "--listed-incremental", newest_incremental + ".copy", "."]
        logger.debug(f"compressions command {' '.join(compression_cmd)}")
        try:
            if not run_cmd(compression_cmd):
                discard_partial(new_backup_loc)
                raise BackupCreateError("tar failed to create the differential backup")
        finally:
            # The working copy of the snapshot must go even when tar failed, or
            # the next run picks it up instead of the real .snar.
            discard_partial(newest_incremental + ".copy")
    else:
        backup_type = "None"

    return backup_type


def create_db_backup(database_config: dict[str, str], result_file: str, pre_prend: list[str] | None = None) -> bool:
    if pre_prend is None:
        pre_prend = []

    bck_cmd = [
        "mariadb-dump",
        "--single-transaction",
        "--user=" + database_config['username'],
        "--password=" + database_config['password'],
        database_config['db_name'],
    ]

    logger.debug(f"creating db backup with cmd: {redact(' '.join(pre_prend + bck_cmd))}")
    suc = False
    try:
        with open(result_file, 'w') as f:
            subprocess.run(pre_prend + bck_cmd, stdout=f, stderr=subprocess.PIPE, text=True, check=True)
            suc = True
    except subprocess.CalledProcessError as e:
        # str(e) contains the whole argv, including --password=..., so it has to
        # be redacted. e.stderr carries the actual mariadb message; the old code
        # read it off a variable that is never assigned when the call raises.
        logger.error(f"Error creating DB backup: {redact(str(e))}")
        logger.error(f"stderr: {redact(e.stderr) if e.stderr else ''}")
        suc = False
    except OSError as e:
        logger.error(f"Could not run mariadb-dump: {redact(str(e))}")
        suc = False
    if suc:
        logger.info("DB backup created")

    return suc
