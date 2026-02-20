import logging
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from utils import run_cmd_with_progress
logger = logging.getLogger(__name__)

def remote_backup(config: dict[str, Any]) -> None:
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
        "--info=progress2",
        str(target_dir)
    ]
    for name, remote in config['remote'].items():
        if not remote['enable']:
            logging.info(f"skipping {name} (disabled)")
            continue
        logging.info(f"Handeling {name}")
        remote_dest = f"{remote['username']}@{remote['address']}:{remote['target_dir']}"
        logging.debug(f"Destination for rsync is {remote_dest}")
        ssh_opts = f"ssh -i {remote['ssh_key']}" if remote.get('ssh_key') else "ssh"
        rsync_cmd_remote = rsync_cmd + ["-e", ssh_opts]
        i = 10 # number of retries
        suc = False
        while i and not suc:
            suc = run_cmd_with_progress(rsync_cmd_remote + [ remote_dest ])
            if not suc:
                sleep_secs = (11-i)*10
                next_try = datetime.now() + timedelta(seconds=sleep_secs)
                logging.warning(f"rsync failed. Retrying at {next_try.strftime('%H:%M:%S')} (in {sleep_secs}s, attempt {11-i} of 10)")
                time.sleep(sleep_secs)
                i -= 1
        if not suc:
            logging.error(f"Copy to remote failed for: {name}")
        else:
            logging.info(f"Copied backups to {name}")
