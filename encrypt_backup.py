import logging
import os
import re
from pathlib import Path
from typing import Any

from utils import ANY_BACKUP_REGEX, PARTIAL_SUFFIX, run_cmd

logger = logging.getLogger(__name__)

def encrypt_backup(config: dict[str, Any], dry_run: bool = False) -> None:
    # Encrypt the backups given the parameters from config
    # Automatically encrypt all backups that are in the target dir
    # Warn:  removes unecrypted version

    target_dir = Path(config['general']['target_dir']).absolute()
    for file in sorted(target_dir.iterdir()):
        if not re.search(ANY_BACKUP_REGEX, file.name):
            logger.debug(f"{file} does not match backup format. Skipping...")
            continue
        if file.name.endswith('.gpg'):
            continue
        encrypted_name = Path(str(file) + ".gpg")
        if encrypted_name.exists():
            logger.info(f"A .gpg file already exists for {file} skipping...")
            continue
        if dry_run:
            logger.info(f"DRY RUN: would encrypt {file}")
            continue

        logger.info(f"encrypting backup {file}")
        # Write to a temporary name and rename only once gpg succeeded. An
        # interrupted run then leaves a .part that no other code looks at,
        # instead of a truncated .gpg that would be taken for a real backup and
        # would make this function skip the file forever.
        partial_name = str(encrypted_name) + PARTIAL_SUFFIX
        logger.debug(f"new file name will be {encrypted_name}")
        # The passphrase is fed via stdin so it never shows up in the
        # process list (encryption of a full backup runs for hours).
        encrypt_cmd: list[str] = [
            'gpg',
            '--batch',
            '--yes',
            '--cipher-algo',
            'AES256',
            '--pinentry-mode',
            'loopback',
            '--passphrase-fd',
            '0',
            '-o',
            partial_name,
            '-c',
            str(file),
        ]
        suc = run_cmd(encrypt_cmd, stdin_data=config['encryption']['password'])
        if not suc:
            logger.error("encrpyion failed")
            remove_partial(partial_name)
            continue
        os.replace(partial_name, encrypted_name)
        logger.debug(f"encrpytion done. deleting unencrypted {file}")
        file.unlink()


def remove_partial(partial_name: str) -> None:
    try:
        os.remove(partial_name)
    except FileNotFoundError:
        pass
    except OSError as e:
        logger.error(f"could not remove the partial file {partial_name}: {e}")
