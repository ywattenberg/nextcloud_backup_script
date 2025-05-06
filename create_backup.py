import logging
import subprocess
import time
from os import path as path
import os
import datetime
import shutil
from typing import List, Optional

from utils import run_cmd, get_newest_file_age, get_docker_prepend, get_newest_files

logger = logging.getLogger(__name__)

def create_backup(config:dict[str, dict[str, str]]) -> Optional[ str ]:
    """
    This function is the top-level function for creating the backup
    it will read the config and determine what if/what kind of backup
    needs to be created and create those backups.
    """
    source_dir:str = config['general']['source_dir'] 
    target_dir:str = config['general']['target_dir'] 
    tmp_dir:str    = config['general']['tmp_dir'] 
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

    d_bt_backups: int = config['general']['days_between_backups'] # type: ignore 
    d_bt_diff_backups:int = config['general']['days_between_diff_backups'] # type: ignore

    age : float = get_newest_file_age(target_dir, r".*-full\.tar\.gz(?:\.gpg)?")
    full_bak_age =  (time.time() - age )/(60*60*24)  
    age : float = get_newest_file_age(target_dir, r".*\.tar\.gz(?:\.gpg)?")
    diff_bak_age = (time.time() - age)/(60*60*24)
    logger.debug(f"newest File found in full backup folder is {full_bak_age} days old, newest differential is {diff_bak_age}")
    full_bak_age -= 0.5 # leave half a day buffer for backup creation
    diff_bak_age -= 0.1 # only tenth a day buffer for differential

    if full_bak_age < float(d_bt_backups) and diff_bak_age < float(d_bt_diff_backups):

        logger.info(f"Newest File found only {full_bak_age}/{d_bt_diff_backups} days old specified age: {d_bt_backups}/{d_bt_diff_backups}. Skipping backup creation...")
        return None
    
    # Enable maintance mode then copy all files:
    logger.info("Creating new backup")
    maintance_cmd : List[str] = config['general']['maintance_cmd'].split(" ") # ignore: typing 
    try:
        # TODO: Change to use docker occ 
        suc = run_cmd(maintance_cmd + ["--on"])
        if not suc:
            logger.error("Could not enable maintance mode. No backup was created. Please check the command in the config")
            raise Exception("Failed to enter maintance")
        logger.info("Enabled Maintance Mode")
        prepend: List[str] = []
        if 'docker' in config and config['docker']['enable']:
            prepend = get_docker_prepend(config['docker'], container_name=config['docker']['db_container_name'])
            logger.debug(f"using docker prepend is: {prepend}")
        
        suc = create_db_backup(config['database'],path.join(tmp_dir, "database_backup.bak"), pre_prend=prepend)
        if not suc:
            logger.error("Failed to create backup of the database. Will continue backing up data")
        else:
            logger.info(f"Created DB backup at {path.join(tmp_dir, "database_backup.bak")}")
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

    if full_bak_age >= float(d_bt_backups): 
        logging.info("creating full backup")
        new_backup_name = datetime.datetime.now().strftime("%Y-%m-%d-%H") + '-full'
        new_backup_loc :str = path.join(target_dir, new_backup_name + ".tar.gz")
        incremental_list:str = path.join(target_dir, new_backup_name + ".snar")
        compression_cmd : List[str] = ["tar", "-C", tmp_dir, "--use-compress-program=\"/usr/bin/pigz\"",  "-cf", new_backup_loc, "--listed-incremental", incremental_list  , "."]
        logger.debug(f"compressions command {' '.join(compression_cmd)}")
        suc = run_cmd(compression_cmd)

    elif diff_bak_age >= float(d_bt_diff_backups):
        logging.info("creating differential backup")
        newest_incremental: str = get_newest_files(target_dir, r".*snar")[0]
        shutil.copy(newest_incremental, newest_incremental + ".copy")

        new_backup_name = datetime.datetime.now().strftime("%Y-%m-%d-%H") + '-differential'
        new_backup_loc :str = path.join(target_dir, new_backup_name + ".tar.gz")
        compression_cmd : List[str] = ["tar", "-C", tmp_dir, "--use-compress-program=\"/usr/bin/pigz\"",  "-cf", new_backup_loc, "--listed-incremental", newest_incremental + ".copy" , "."]
        logger.debug(f"compressions command {' '.join(compression_cmd)}")
        suc = run_cmd(compression_cmd)

        os.remove(newest_incremental + ".copy")


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
        logger.error(f"Error creating DB backup: {e}")
        logger.error(f"stderr: {res.stderr}")
        suc = False
    if suc:
        logger.info("DB backup created")

    return suc




