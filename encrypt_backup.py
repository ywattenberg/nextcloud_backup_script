import logging
from pathlib import Path
from typing import Any
import re
from utils import run_cmd

logger = logging.getLogger(__name__)

def encrypt_backup(config: dict[str, Any]) -> None:
    # Encrypt the backups given the parameters from config
    # Automatically encrypt all backups that are in the target dir
    # Warn:  removes unecrypted version

    target_dir = Path(config['general']['target_dir']).absolute()
    regex = r".*\.tar\.gz"
    for file in target_dir.iterdir():
        if not re.search(regex, file.name):
            logger.debug(f"{file} does not match backup format. Skipping...")
        elif not file.name.endswith('.gpg'):
            # Test if file already encpy
            if Path(str(file) + ".gpg").exists():
                logging.info(f"A .gpg file already exists for {file} skipping...")
                continue
            logger.info(f"encrypting backup {file}")
            encrypted_name = str(file) + ".gpg"
            logger.debug(f"new file name will be {encrypted_name}")
            encrypt_cmd: list[str] = [
                'gpg',
                '--batch',
                '--yes',
                '--cipher-algo',
                'AES256',
                '--passphrase',
                config['encryption']['password'],
                '-o',
                encrypted_name,
                '-c',
                str(file),
            ]
            suc = run_cmd(encrypt_cmd)
            if suc:
                logger.debug(f"encrpytion done. deleting unencrypted {file}")
                file.unlink()
            else:
                logger.error("encrpyion failed")
