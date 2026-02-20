import logging
import datetime
import os
from typing import Any

from utils import get_newest_files

logger = logging.getLogger(__name__)

def purge_backups(config: dict[str, Any]) -> None:
    target_dir: str = config['general']['target_dir']
    target_dir = os.path.abspath(target_dir)
    num_full: int = int(config['general']['num_full_backups'])

    # Manage full backups:
    full_backups = get_newest_files(target_dir, r".*-full\.tar\.gz(?:\.gpg)?")

    if num_full >= len(full_backups):
        logger.info(f"only found {len(full_backups)} full backups not removing any")
    else:
        bks_to_remove = full_backups[num_full:]
        logger.debug(f"found the following backups to remove {bks_to_remove}")
        logger.info(f"found {len(bks_to_remove)} backups to remove")
        for bk in bks_to_remove:
            os.remove(os.path.join(target_dir, bk))

        # Clean up differentials left over
        oldest_kept_backup = os.path.basename(full_backups[num_full - 1])
        oldest_date = datetime.datetime.strptime(oldest_kept_backup.split('.')[0].replace("-full",""), "%Y-%m-%d-%H")

        all_files = os.listdir(target_dir)
        differential = [file for file in all_files if "diff" in file]
        for backup in differential:
            time_str = backup.split(".")[0].replace("-differential","")
            parsed_time = datetime.datetime.strptime(time_str, "%Y-%m-%d-%H")
            if parsed_time < oldest_date:
                logger.debug(f"""age of differentia backup {backup} older than oldest kept full backup. deleting...""")
                os.remove(os.path.join(target_dir, backup))
