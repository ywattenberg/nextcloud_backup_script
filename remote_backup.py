import logging
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from utils import run_cmd_with_progress
logger = logging.getLogger(__name__)

def remote_backup(config: dict[str, Any]) -> dict[str, bool]:
    """Copy the backup dir to every enabled remote.

    Returns whether the copy succeeded per remote name. purge_remote needs this:
    rsync writes with --append --inplace, so a failed transfer leaves a
    truncated file under the final name, and purging against that listing would
    count the truncated file as a restore point.
    """
    # TODO: add support for running command after copy

    # simply rsync the whole backup folder to remote wihtout --delete
    # such that remote machine can manage the backups it self
    # or we can add options in config
    logging.debug("Starting copying to remote location")
    results: dict[str, bool] = {}
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
            results[name] = False
            continue
        logging.info(f"Handeling {name}")
        remote_dest = f"{remote['username']}@{remote['address']}:{remote['target_dir']}"
        logging.debug(f"Destination for rsync is {remote_dest}")
        ssh_opts = f"ssh -i {remote['ssh_key']}" if remote.get('ssh_key') else "ssh"
        rsync_cmd_remote = rsync_cmd + ["-e", ssh_opts]
        if remote.get('run_as'):
            rsync_cmd_remote = ["sudo", "-u", remote['run_as']] + rsync_cmd_remote
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
        results[name] = suc
        if not suc:
            logging.error(f"Copy to remote failed for: {name}")
        else:
            logging.info(f"Copied backups to {name}")
    return results
