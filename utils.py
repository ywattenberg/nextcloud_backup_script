from typing import List, Optional
import os
import re
import logging
import subprocess
import time

logger = logging.getLogger(__name__)


def get_docker_prepend(docker_config: dict[str, str], user:Optional[str]=None, container_name:Optional[str]=None) -> List[str]:
    if not container_name:
        container_name = docker_config['container_name']
    return  [
        "/usr/bin/docker",
        "compose",
        "-f",
        docker_config['compose_file'],
        "exec",
        container_name,
    ] + (["--user", user,] if user else [])


def run_cmd(cmd:List[str], shell:bool=False) -> bool:
    try: 
        res = subprocess.run(cmd, capture_output=True, shell=shell)
        logger.debug(f"Ran command {' '.join(cmd)}")
        res.check_returncode()
    except subprocess.CalledProcessError as e:
        logger.error(f"An exception occurred while executing the command: {' '.join(cmd)}")
        logger.error(f"Stderr: {res.stderr.decode() if res and res.stderr else ''}")
        logger.error(f"Exception: {e}")
        return False
    return True

def run_cmd_with_progress(cmd:List[str], log_interval:int=30) -> bool:
    logger.info(f"Running command with progress: {' '.join(cmd)}")
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        last_log_time = time.time()
        last_progress_line = ""
        assert proc.stdout is not None
        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue
            last_progress_line = line
            now = time.time()
            if now - last_log_time >= log_interval:
                logger.info(f"Progress: {line}")
                last_log_time = now
        proc.wait()
        if proc.returncode != 0:
            stderr = proc.stderr.read() if proc.stderr else ""
            logger.error(f"Command failed with return code {proc.returncode}: {' '.join(cmd)}")
            logger.error(f"Stderr: {stderr}")
            return False
        if last_progress_line:
            logger.info(f"Final progress: {last_progress_line}")
        logger.info(f"Command completed successfully: {' '.join(cmd)}")
    except Exception as e:
        logger.error(f"An exception occurred while executing: {' '.join(cmd)}")
        logger.error(f"Exception: {e}")
        return False
    return True


def get_newest_files(directory:str, regex:str=r".*", exclude_regex:Optional[ str ]=None)->List[str]:
    """Get newest file in directory.

    Args:
        directory (str): Directory to seerch

    Returns:
        List[str]: list of all files matching regex and not matching exlude regex
                   sorted by there age
    """
    logger.debug(f"Searching files in dir {directory}")
    files = os.listdir(directory)
    regex_pattern = re.compile(regex)
    files = [os.path.join(directory, file) for file in files if regex_pattern.search(file)]
    logger.debug(f"Found the following files {files}")
    if exclude_regex:
        exclude_regex_pattern = re.compile(exclude_regex)
        files = [os.path.join(directory, file) for file in files if not exclude_regex_pattern.search(file)]
    files.sort(key=os.path.getmtime)
    files.reverse()
    return files

def get_newest_file_age(directory:str, regex:str=r".*", exclude_regex:Optional[str]=None) -> float:
    """Get age of newest file in directory.

    Args:
        directory (str): Directory to search

    Returns:
        float: Age of newest file in directory 
    """
    files = get_newest_files(directory, regex, exclude_regex)
    if files:
        logger.debug(f"newest file found in {directory} is {files[0]}")
        return os.path.getmtime(files[0])
    logger.debug(f"No files in {directory} found returning default value (-1)")
    return -1.0
