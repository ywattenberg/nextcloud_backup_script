import logging
import time
from pathlib import Path

from utils import run_cmd
logger = logging.getLogger(__name__)

def remote_backup(config: dict[str, dict[str,str]]):
    # TODO: add support for running command after copy 

    # simply rsync the whole backup folder to remote wihtout --delete
    # such that remote machine can manage the backups it self
    # or we can add options in config
    logging.debug("Starting copying to rmeote location")
    target_dir = Path(config['general']['target_dir']).absolute()
    rsync_cmd = [
        "rsync",
        "-av",
        "--append",
        "--inplace",
        str(target_dir)
    ] 
    for name, remote in config['remote'].items():
        if not remote['enable']:
            logging.info(f"skipping {name} (disabled)")
            continue
        logging.info(f"Handeling {name}")
        remote_dest = f"{remote['username']}@{remote['address']}:{remote['target_dir']}" # type:ignore
        logging.debug(f"Destination for rsync is {remote_dest}")
        i = 10 # number of retries
        suc = False
        while i and not suc:
            suc = run_cmd(rsync_cmd + [ remote_dest ])
            if not suc:
                logging.debug("rsync failed. sleeping and retry")
                time.sleep((11-i)*10) 
        if not suc:
            logging.error(f"Copy to remote failed for: {name}")
        else:
            logging.info(f"Copied backups to {name}")

