import logging
from pathlib import Path
from typing import List
import re
from utils import run_cmd

logger = logging.getLogger(__name__)
def encrypt_backup(config: dict[str, dict[str,str]]):
    # Encrypt the backups given the parameters from config
    # Automatically encrypt all backups that are in the target dir
    # Warn:  removes unecrypted version
    
    target_dir = Path(config['general']['target_dir']).absolute()
    regex = r".*\.tar\.gz"
    for file in target_dir.iterdir():
        if not re.search(regex, file.name):
            logger.debug(f"{file} does not match backup format. Skipping...")
        elif not file.name.endswith('.gpg'):
            logger.info(f"encrypting backup {file}")
            encrypted_name = file.name + ".gpg"
            logger.debug(f"new file name will be {encrypted_name}")
            encrypt_cmd: List[str] = [
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
            
