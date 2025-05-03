from typing import List, Optional
import os
import re
import logging
import subprocess

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
        logger.error(f"Stderr: {res.stderr if res else ''}")
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
    regex_pattern = re.compile(regex.encode('unicode_escape').decode())
    files = [os.path.join(directory, file) for file in files if regex_pattern.search(file)]
    logger.debug(f"Found the following files {files}")
    if exclude_regex:
        exclude_regex_pattern = re.compile(exclude_regex.encode('unicode_escape').decode())
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
