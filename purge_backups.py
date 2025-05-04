import logging
import datetime
import os
from utils import get_newest_files

logger = logging.getLogger(__name__)

def purge_backups(config: dict[str, dict[str, str]]):
    target_dir:str = config['general']['target_dir'] 
    target_dir = os.path.abspath(target_dir) # type: ignore 
    num_full:int = int(config['general']['num_full_backups'])
    # num_diff:int = int( config['general']['num_differential_backups']  )

    # Manage full backups:
    full_backups = get_newest_files(target_dir, r".*-full\.tar\.gz(?:\.gpg)?")

    if num_full >= len(full_backups):
        logging.info(f"only found {len(full_backups)} full backups not removing any")
    else:
        bks_to_remove = full_backups[num_full:]
        logging.debug(f"found the following backups to remove {bks_to_remove}")
        logging.info(f"found {len(bks_to_remove)} backups to remove")
        [os.remove(os.path.join(target_dir, bk)) for bk in bks_to_remove]

        # Clean up differentials left over
        oldest_kept_backup = os.path.basename( full_backups[num_full - 1] )
        oldest_date = datetime.datetime.strptime(oldest_kept_backup.split('.')[0].replace("-full",""), "%Y-%m-%d-%H")

        all_files = os.listdir(target_dir)
        differential = [file for file in all_files if "diff" in file]
        for backup in differential:
            time = backup.split(".")[0].replace("-differential","")
            parsed_time = datetime.datetime.strptime(time, "%Y-%m-%d-%H")
            if parsed_time < oldest_date:
                logging.debug(f"""age of differentia backup {backup} older than oldest kept full backup. deleting...""")
                os.remove(os.path.join(target_dir,backup))

        # TODO: Add removing of differential backups

