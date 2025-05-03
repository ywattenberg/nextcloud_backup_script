import logging
import subprocess
import time
from os import path as path
import os
import multiprocessing
import datetime
from typing import List, Optional
import json

from utils import run_cmd, get_newest_file_age, get_docker_prepend

logger = logging.getLogger(__name__)

def create_backup(config:dict[str, dict[str, str]]) -> Optional[ str ]:
    """
    This function is the top-level function for creating the backup
    it will read the config and determine what if/what kind of backup
    needs to be created and create those backups.
    """
    # TODO: Remove
    logging.debug(f"Config: {json.dumps(config, indent='  ')}")
    source_dir:str = config['general']['source_dir'] #ignore: typing
    target_dir:str = config['general']['target_dir'] # ignore: typing
    tmp_dir:str    = config['general']['tmp_dir'] # ignore: typing
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

    d_bt_backups: int = config['general']['days_between_backups'] # ignore:typing
    age : float = get_newest_file_age(target_dir)
    age_in_days = int((time.time() - age)/(60*60*24))
    logger.debug(f"newest File found in backup folder is {age_in_days} days old")


    if age_in_days < d_bt_backups:
        logger.info(f"Newest File found only {age_in_days} days old. Skipping backup creation...")
        return None
    
    # Need to create a new backup at the moment only do full backups...
    # Enable maintance mode then copy all files:
    logger.info("Creating new backup")
    new_backup_name = datetime.datetime.now().strftime("%Y-%m-%d-%H")

    maintance_cmd : List[str] = config['general']['maintance_cmd'].split(" ") # ignore: typing 
    try:
        suc = run_cmd(maintance_cmd + ["--on"])
        if not suc:
            logger.error("Could not enable maintance mode. No backup was created. Please check the command in the config")
            raise Exception("Failed to enter maintance")
        logger.info("Enabled Maintance Mode")
        prepend: List[str] = []
        if 'docker' in config and config['docker']['enable']:
            prepend = get_docker_prepend(config['docker'], container_name=config['docker']['db_container_name'])
            logging.debug(f"using docker prepend is: {prepend}")
        
        suc = create_db_backup(config['database'],path.join(tmp_dir, "database_backup.bak"), pre_prend=prepend)
        if not suc:
            logging.error("Failed to create backup of the database. Will continue backing up data")
        else:
            logging.info(f"Created DB backup at {path.join(tmp_dir, "database_backup.bak")}")
        # Copy files to tmp dir using rsync
        rsync_cmd = ["rsync", "-av", "--delete", source_dir, tmp_dir] 
        logger.debug(f"Copying source folder: {source_dir} to tmp dir {tmp_dir} using command: {' '.join(rsync_cmd)}")
        suc = run_cmd(rsync_cmd)
        if not suc:
            logger.error("rsync command failed.")
            raise Exception("Failed to copy files")
        logger.debug("Copy done")
    finally:
        # Disable maintance mode
        tries = 0
        suc:bool = False
        while tries < 10 and not suc:
            suc = run_cmd(maintance_cmd + ["--off"])
            tries += 1
        if not suc:
            logger.fatal("Could not disable maintance mode manual intervention required")
            raise Exception("failed to disable maintance mode") 

    logger.info("Done with Maintance. Compressing backup to final location")

    new_backup_loc :str = path.join(target_dir, new_backup_name + ".tar.gz")
    cpu_count = str(max(4, multiprocessing.cpu_count() - 5))

    compression_cmd : List[str] = ["tar", "--absolute-names", "--use-compress-program=\"/usr/bin/pigz -k -p {cpu_count}\"",  "-cf", new_backup_loc , tmp_dir]
    logger.debug(f"compressions command {' '.join(compression_cmd)}")
    suc = run_cmd(compression_cmd)


def create_db_backup(database_config: dict[str, str], result_file:str, pre_prend:List[str] = []) -> bool:
    bck_cmd =[
        "mariadb-dump",
        "--single-transaction",
        "--user=" +  database_config['username'],
        "--password=" + database_config['password'],
        database_config['db_name'],
    ]

    logger.debug(f"creating db backup with cmd: {' '.join(pre_prend + bck_cmd)}")
    try:
        with open(result_file, 'w') as f:
            res = subprocess.run(pre_prend + bck_cmd, stdout=f, text=True, check=True)
            suc = True
    except subprocess.CalledProcessError as e:
        logging.error(f"Error creating DB backup: {e}")
        logging.error(f"stderr: {res.stderr}")
        suc = False
    if suc:
        logger.info("DB backup created")

    return suc

