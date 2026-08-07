from typing import List, Optional
from datetime import datetime
import os
import re
import logging
import subprocess
import time

logger = logging.getLogger(__name__)

_SECRETS: List[str] = []
REDACTED = "***REDACTED***"

# Naming scheme of the artefacts in the backup dir, e.g.
# 2026-08-06-01-full.tar.gz.gpg / 2026-08-06-01-differential.tar.gz / 2026-08-06-01-full.snar
FULL_BACKUP_REGEX = r".*-full\.tar\.gz(?:\.gpg)?$"
DIFF_BACKUP_REGEX = r".*-differential\.tar\.gz(?:\.gpg)?$"
SNAR_REGEX = r".*\.snar$"


def backup_prefix(name: str) -> str:
    """Strip directory and suffixes: '<dir>/2026-08-06-01-full.tar.gz.gpg' -> '2026-08-06-01-full'."""
    return os.path.basename(name).split('.')[0]


def backup_timestamp(name: str) -> Optional[datetime]:
    """Parse the creation time out of a backup file name, None if it does not fit the scheme."""
    stamp = backup_prefix(name).replace("-full", "").replace("-differential", "")
    try:
        return datetime.strptime(stamp, "%Y-%m-%d-%H")
    except ValueError:
        logger.warning(f"Could not read a timestamp from {name}. It will be left alone.")
        return None


def register_secrets(*secrets: Optional[str]) -> None:
    """Register values that must never end up in the log file.

    Everything logged by run_cmd/run_cmd_with_progress is passed through
    redact(), so registering here covers all current and future call sites.
    """
    for secret in secrets:
        if secret and secret not in _SECRETS:
            _SECRETS.append(secret)


def redact(text: str) -> str:
    """Replace every registered secret in text with a placeholder."""
    for secret in _SECRETS:
        text = text.replace(secret, REDACTED)
    return text


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


def run_cmd(cmd:List[str], shell:bool=False, stdin_data:Optional[str]=None) -> bool:
    res: Optional[subprocess.CompletedProcess[bytes]] = None
    try:
        res = subprocess.run(
            cmd,
            capture_output=True,
            shell=shell,
            input=stdin_data.encode() if stdin_data is not None else None,
        )
        logger.debug(f"Ran command {redact(' '.join(cmd))}")
        res.check_returncode()
    except subprocess.CalledProcessError as e:
        logger.error(f"An exception occurred while executing the command: {redact(' '.join(cmd))}")
        logger.error(f"Stderr: {redact(res.stderr.decode()) if res and res.stderr else ''}")
        logger.error(f"Exception: {redact(str(e))}")
        return False
    except OSError as e:
        # e.g. the binary does not exist -- would otherwise abort the whole run
        logger.error(f"Could not execute the command: {redact(' '.join(cmd))}")
        logger.error(f"Exception: {redact(str(e))}")
        return False
    return True


def run_cmd_output(cmd:List[str]) -> Optional[str]:
    """Run a command and return its stdout, or None if it failed."""
    try:
        res = subprocess.run(cmd, capture_output=True, text=True)
        logger.debug(f"Ran command {redact(' '.join(cmd))}")
        res.check_returncode()
    except subprocess.CalledProcessError as e:
        logger.error(f"An exception occurred while executing the command: {redact(' '.join(cmd))}")
        logger.error(f"Stderr: {redact(res.stderr) if res.stderr else ''}")
        logger.error(f"Exception: {redact(str(e))}")
        return None
    except OSError as e:
        logger.error(f"Could not execute the command: {redact(' '.join(cmd))}")
        logger.error(f"Exception: {redact(str(e))}")
        return None
    return res.stdout

def run_cmd_with_progress(cmd:List[str], log_interval:int=30) -> bool:
    logger.info(f"Running command with progress: {redact(' '.join(cmd))}")
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
                logger.info(f"Progress: {redact(line)}")
                last_log_time = now
        proc.wait()
        if proc.returncode != 0:
            stderr = proc.stderr.read() if proc.stderr else ""
            logger.error(f"Command failed with return code {proc.returncode}: {redact(' '.join(cmd))}")
            logger.error(f"Stderr: {redact(stderr)}")
            return False
        if last_progress_line:
            logger.info(f"Final progress: {redact(last_progress_line)}")
        logger.info(f"Command completed successfully: {redact(' '.join(cmd))}")
    except Exception as e:
        logger.error(f"An exception occurred while executing: {redact(' '.join(cmd))}")
        logger.error(f"Exception: {redact(str(e))}")
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
